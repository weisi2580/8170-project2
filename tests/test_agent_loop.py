"""Offline test of the Claude tool-use loop with a scripted fake client."""

from types import SimpleNamespace as NS

import pytest

from tbm import claude_agent
from tbm.claude_agent import Finished, Tool


def _resp(content, stop="tool_use"):
    usage = NS(input_tokens=10, output_tokens=5, cache_read_input_tokens=0,
               cache_creation_input_tokens=0)
    return NS(content=content, stop_reason=stop, stop_details=None, model="fake",
              usage=usage, _request_id="req_x")


class FakeClient:
    def __init__(self, script):
        self.script = list(script)
        self.requests = []
        self.beta = NS(messages=NS(create=self._create))

    def _create(self, **kw):
        self.requests.append(kw)
        return self.script.pop(0)


def test_loop_runs_tools_reports_errors_and_finishes(tmp_path):
    calls = []

    def add(a: int, b: int):
        calls.append((a, b))
        return {"sum": a + b}

    def done(answer: str):
        raise Finished(answer)

    tools = [Tool("add", "add", {"a": {"type": "integer"}, "b": {"type": "integer"}}, add),
             Tool("done", "finish", {"answer": {"type": "string"}}, done)]
    script = [
        _resp([NS(type="thinking", thinking="plan: add"), NS(type="text", text="Adding."),
               NS(type="tool_use", id="t1", name="add", input={"a": 2, "b": 3}),
               NS(type="tool_use", id="t2", name="nope", input={})]),
        _resp([NS(type="tool_use", id="t3", name="done", input={"answer": "5"})]),
    ]
    client = FakeClient(script)
    run = claude_agent.run_agent("test", "sys", "task", tools, tmp_path, client=client)

    assert run.result == "5" and run.steps == 2 and calls == [(2, 3)]
    results = client.requests[1]["messages"][2]["content"]  # task, assistant, results
    assert [r["tool_use_id"] for r in results] == ["t1", "t2"]  # one user turn, both results
    assert results[1]["is_error"] and "unknown tool" in results[1]["content"]
    schema = client.requests[0]["tools"][0]
    assert schema["strict"] and schema["input_schema"]["additionalProperties"] is False
    md = (tmp_path / "agent_transcript.md").read_text()
    assert "plan: add" in md and "`add`" in md


def test_loop_stops_on_refusal(tmp_path):
    client = FakeClient([_resp([], stop="refusal")])
    with pytest.raises(RuntimeError, match="declined"):
        claude_agent.run_agent("test", "sys", "task", [], tmp_path, client=client)


def test_require_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    with pytest.raises(SystemExit, match="--baseline"):
        claude_agent.require()
