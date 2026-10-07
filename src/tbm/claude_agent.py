"""Claude agent layer: a tool-use loop that lets Claude drive Agent 1 and Agent 2.

Claude decides what to do next (search settings, which templates to try, which model to keep,
what the errors mean); the tools do the computation (HMMER, MODELLER, metrics) and
enforce the hard rules (leakage control, no ground truth in Agent 1). Every step, with
Claude's reasoning summary, tool inputs and results, is written to a transcript.

Credentials: ANTHROPIC_API_KEY from https://platform.claude.com/settings/keys, plus
ANTHROPIC_WORKSPACE_ID (wrkspc_…) when the key is a user key (sk-ant-usr-…) that isn't
scoped to a workspace. `--baseline` runs without Claude.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

MODEL = os.environ.get("TBM_CLAUDE_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("TBM_CLAUDE_EFFORT", "high")
MAX_STEPS = 40
LOG_RESULT_CHARS = 4000  # tool results are truncated in the markdown transcript only

INTERPRET_SYSTEM = """\
You are the coordinating agent of a template-based protein structure modeling pipeline. \
You are given, for three CASP15 targets of increasing difficulty, the MODELLER and \
AlphaFold3 scores against the experimental structure over the CASP evaluation unit, the \
agent's template decisions, Agent 2's per-target analyses, and (when present) the scores \
of a score-only baseline run without an agent. Write the results interpretation for a \
course project report: connect MODELLER's accuracy to template identity, coverage and \
alignment quality, compare with AlphaFold3, say whether the agent's decisions changed the \
outcome relative to the baseline, and note caveats (missing models, no-template targets, \
three targets only). Use only the numbers given; do not invent values. Markdown, about \
400-600 words, no title heading."""


def baseline_mode() -> bool:
    return bool(os.environ.get("TBM_BASELINE"))


def require() -> None:
    """Exit with instructions unless Claude can be called."""
    try:
        import anthropic  # noqa: F401
    except ImportError:
        raise SystemExit("The anthropic package is missing: pip install 'anthropic>=1.0'")
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        raise SystemExit(
            "ANTHROPIC_API_KEY is not set. Agents 1 and 2 are run by Claude; create a "
            "workspace-scoped key at https://platform.claude.com/settings/keys and export it, "
            "or pass --baseline for the score-only run without an agent.")


def _client():
    """User keys (sk-ant-usr-…) aren't tied to a workspace; ANTHROPIC_WORKSPACE_ID names one."""
    import anthropic
    ws = os.environ.get("ANTHROPIC_WORKSPACE_ID")
    return anthropic.Anthropic(default_headers={"anthropic-workspace-id": ws} if ws else None)


def _request(client, **kwargs):
    return client.beta.messages.create(
        model=MODEL,
        max_tokens=16000,
        thinking={"type": "adaptive", "display": "summarized"},
        output_config={"effort": EFFORT},
        cache_control={"type": "ephemeral"},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        **kwargs,
    )


@dataclass
class Tool:
    name: str
    description: str
    properties: dict
    fn: Callable[..., object]
    required: list[str] | None = None

    def schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "strict": True,
            "input_schema": {
                "type": "object",
                "properties": self.properties,
                "required": self.required if self.required is not None else list(self.properties),
                "additionalProperties": False,
            },
        }


class Finished(Exception):
    """Raised by a tool to end the run; its argument becomes the run's result."""


@dataclass
class AgentRun:
    result: object = None
    steps: int = 0
    usage: dict = field(default_factory=lambda: {"input_tokens": 0, "output_tokens": 0,
                                                 "cache_read_input_tokens": 0,
                                                 "cache_creation_input_tokens": 0})
    model: str = MODEL
    request_ids: list[str] = field(default_factory=list)


def _fmt_result(obj) -> str:
    return obj if isinstance(obj, str) else json.dumps(obj, indent=1, default=str)


def run_agent(name: str, system: str, task: str, tools: list[Tool], log_dir: Path,
              client=None, max_steps: int = MAX_STEPS) -> AgentRun:
    """Manual tool-use loop. Ends when a tool raises Finished or Claude stops calling tools."""
    client = client or _client()
    by_name = {t.name: t for t in tools}
    messages: list = [{"role": "user", "content": task}]
    run = AgentRun()
    log_dir.mkdir(parents=True, exist_ok=True)
    md = [f"# {name}: agent transcript", "",
          f"- model: {MODEL}, effort: {EFFORT}",
          f"- started: {datetime.now(timezone.utc).isoformat(timespec='seconds')}", "",
          "## Task", "", task, ""]
    jsonl = open(log_dir / "agent_transcript.jsonl", "w")

    def log(event: dict) -> None:
        jsonl.write(json.dumps(event, default=str) + "\n")
        jsonl.flush()

    def say(msg: str) -> None:
        print(f"[{name}] {msg}")

    try:
        while run.steps < max_steps:
            run.steps += 1
            resp = _request(client, system=system, messages=messages,
                            tools=[t.schema() for t in tools])
            run.model = resp.model
            run.request_ids.append(resp._request_id)
            for k in run.usage:
                run.usage[k] += getattr(resp.usage, k, 0) or 0
            md.append(f"## Step {run.steps}")
            md.append("")
            for b in resp.content:
                if b.type == "thinking" and b.thinking:
                    md += ["**Reasoning (summary):**", "", b.thinking, ""]
                    log({"step": run.steps, "type": "thinking", "text": b.thinking})
                elif b.type == "text" and b.text.strip():
                    md += [b.text, ""]
                    log({"step": run.steps, "type": "text", "text": b.text})
                    say(b.text.strip().splitlines()[0][:160])

            if resp.stop_reason == "refusal":
                raise RuntimeError(f"Claude declined the request: {resp.stop_details}")
            if resp.stop_reason == "max_tokens":
                raise RuntimeError("Claude's response hit max_tokens")
            calls = [b for b in resp.content if b.type == "tool_use"]
            messages.append({"role": "assistant", "content": resp.content})
            if not calls:
                if resp.stop_reason == "pause_turn":
                    continue
                messages.append({"role": "user", "content":
                                 "Continue: call the finishing tool when you are done."})
                continue

            results, finished = [], None
            for call in calls:
                args = call.input if isinstance(call.input, dict) else {}
                md += [f"**Tool call** `{call.name}`", "", "```json",
                       json.dumps(args, indent=1), "```", ""]
                log({"step": run.steps, "type": "tool_use", "name": call.name, "input": args})
                say(f"-> {call.name}({', '.join(f'{k}={v!r}' for k, v in args.items() if k not in ('rationale', 'analysis_markdown'))})")
                tool = by_name.get(call.name)
                is_error = False
                try:
                    if tool is None:
                        raise ValueError(f"unknown tool {call.name}")
                    out = _fmt_result(tool.fn(**args))
                except Finished as f:
                    finished = f.args[0] if f.args else None
                    out = "Recorded. The run is complete."
                except Exception as e:  # report tool failures back to Claude
                    out, is_error = f"{type(e).__name__}: {e}", True
                    say(f"   tool error: {out[:200]}")
                log({"step": run.steps, "type": "tool_result", "name": call.name,
                     "is_error": is_error, "content": out})
                shown = out if len(out) <= LOG_RESULT_CHARS else out[:LOG_RESULT_CHARS] + "\n…"
                md += [f"**Result**{' (error)' if is_error else ''}:", "", "```",
                       shown, "```", ""]
                results.append({"type": "tool_result", "tool_use_id": call.id,
                                "content": out, "is_error": is_error})
            messages.append({"role": "user", "content": results})
            if finished is not None:
                run.result = finished
                break
        else:
            raise RuntimeError(f"{name}: no result after {max_steps} steps")
    finally:
        md += ["## Usage", "", f"- steps: {run.steps}",
               *(f"- {k}: {v}" for k, v in run.usage.items()),
               f"- request ids: {', '.join(r for r in run.request_ids if r)}", ""]
        (log_dir / "agent_transcript.md").write_text("\n".join(md))
        jsonl.close()
    return run


def interpret_results(payload: dict) -> str:
    """Single call: draft the results-interpretation section from the collected outputs."""
    resp = _request(_client(), system=INTERPRET_SYSTEM, messages=[
        {"role": "user", "content": json.dumps(payload, indent=1, default=str)}])
    if resp.stop_reason in ("refusal", "max_tokens"):
        raise RuntimeError(f"interpretation stopped: {resp.stop_reason}")
    return "".join(b.text for b in resp.content if b.type == "text").strip()
