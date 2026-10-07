"""Aggregate Agent 1 / Agent 2 outputs into the results table."""

from __future__ import annotations

import csv
import json

from . import claude_agent
from .config import RESULTS, Config, results_root
from .visualize import METHODS, summary_plot

COLUMNS = ["target", "difficulty", "method", "tm_score", "gdt_ts", "lddt", "rmsd",
           "template", "template_identity", "template_coverage", "align2d_identity",
           "align2d_coverage", "dope", "af3_ranking_score", "af3_mean_plddt"]


def collect(config: Config) -> list[dict]:
    rows = []
    for t in config.targets.values():
        m_path = t.result_dir / "agent2" / "metrics.json"
        if not m_path.exists():
            continue
        metrics = json.loads(m_path.read_text())
        d_path = t.result_dir / "agent1" / "decision.json"
        decision = json.loads(d_path.read_text()) if d_path.exists() else {}
        tpl = decision.get("template", {})
        mod = decision.get("modeller", {})
        for method in METHODS:
            res = metrics["methods"].get(method)
            if not res:
                continue
            row = {
                "target": t.id, "difficulty": t.difficulty, "method": method,
                "tm_score": res["tm_score"], "gdt_ts": res["gdt_ts"],
                "lddt": res["lddt"], "rmsd": res["rmsd"],
            }
            if method == "MODELLER":
                row.update({
                    "template": f"{tpl.get('entry_id', '')}:{tpl.get('chain', '')}",
                    "template_identity": tpl.get("identity"),
                    "template_coverage": tpl.get("coverage"),
                    "align2d_identity": mod.get("alignment", {}).get("identity"),
                    "align2d_coverage": mod.get("alignment", {}).get("coverage"),
                    "dope": mod.get("best", {}).get("dope"),
                })
            else:
                row.update({"af3_ranking_score": res.get("ranking_score"),
                            "af3_mean_plddt": res.get("mean_ca_bfactor")})
            rows.append(row)
    return rows


def _fmt(v, nd=3):
    if v is None or v == "":
        return "–"
    if isinstance(v, float):
        return f"{v:.{nd}f}"
    return str(v)


def _baseline_rows() -> list[dict]:
    p = RESULTS / "baseline" / "summary.csv"
    if not p.exists():
        return []
    with open(p) as fh:
        return list(csv.DictReader(fh))


def write(config: Config) -> list[dict]:
    rows = collect(config)
    root = results_root()
    baseline = claude_agent.baseline_mode()
    root.mkdir(parents=True, exist_ok=True)
    with open(root / "summary.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    title = "Results: score-only baseline (no agent)" if baseline else "Results: Claude agents"
    md = [f"# {title}", "",
          "Scores over the CASP evaluation unit; TM-score/GDT-TS/lDDT higher is better, "
          "RMSD (CA, all common residues) lower is better.", "",
          "| Target | Difficulty | Method | TM | GDT-TS | lDDT | RMSD (Å) |",
          "|---|---|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['target']} | {r['difficulty']} | {r['method']} | {_fmt(r['tm_score'])} "
                  f"| {_fmt(r['gdt_ts'], 1)} | {_fmt(r['lddt'])} | {_fmt(r['rmsd'], 2)} |")
    md += ["", "## Template signal (MODELLER)", "",
           "| Target | Template | Identity | Coverage | align2d identity | align2d coverage "
           "| DOPE |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        if r["method"] == "MODELLER":
            md.append(f"| {r['target']} | {r['template']} | {_fmt(r['template_identity'])} "
                      f"| {_fmt(r['template_coverage'])} | {_fmt(r['align2d_identity'])} "
                      f"| {_fmt(r['align2d_coverage'])} | {_fmt(r['dope'], 1)} |")
    base = [] if baseline else _baseline_rows()
    base_m = {b["target"]: b for b in base if b["method"] == "MODELLER"}
    if base_m:
        md += ["", "## MODELLER: Claude agent vs score-only baseline", "",
               "| Target | Agent template | Agent TM | Baseline template | Baseline TM "
               "| Agent GDT-TS | Baseline GDT-TS |", "|---|---|---|---|---|---|---|"]
        for r in rows:
            b = base_m.get(r["target"])
            if r["method"] == "MODELLER" and b:
                md.append(f"| {r['target']} | {r['template']} | {_fmt(r['tm_score'])} "
                          f"| {b['template']} | {_fmt(float(b['tm_score']))} "
                          f"| {_fmt(r['gdt_ts'], 1)} | {_fmt(float(b['gdt_ts']), 1)} |")
    (root / "summary.md").write_text("\n".join(md) + "\n")
    if rows:
        summary_plot(rows, root / "summary_metrics.png")
    if rows and not baseline:
        claude_agent.require()
        payload = {"results": rows, "baseline_results": base,
                   "agent1_decisions": _decision_digest(config),
                   "agent2_analyses": {t.id: (t.result_dir / "agent2" / "analysis.md").read_text()
                                       for t in config.targets.values()
                                       if (t.result_dir / "agent2" / "analysis.md").exists()}}
        text = claude_agent.interpret_results(payload)
        (root / "interpretation.md").write_text(
            f"# Interpretation (drafted by {claude_agent.MODEL})\n\n{text}\n")
        print("Claude interpretation -> results/interpretation.md")
    return rows


def _decision_digest(config: Config) -> dict:
    out = {}
    for t in config.targets.values():
        p = t.result_dir / "agent1" / "decision.json"
        if not p.exists():
            continue
        d = json.loads(p.read_text())
        out[t.id] = {
            "status": d.get("status"), "selected_by": d.get("selected_by"),
            "searches": d.get("searches"), "rationale": d.get("rationale"),
            "template": {k: d.get("template", {}).get(k) for k in
                         ("entry_id", "chain", "identity", "coverage", "query_beg", "query_end")},
            "align2d": d.get("modeller", {}).get("alignment"),
            "selected_model": d.get("modeller", {}).get("best"),
        }
    return out
