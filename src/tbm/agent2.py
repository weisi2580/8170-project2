"""Agent 2: evaluation of the MODELLER and AlphaFold3 models against the experimental structure.

All structures are mapped onto target-sequence numbering by sequence alignment, trimmed to
the CASP evaluation unit (EU), and compared with a fixed residue correspondence.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from . import af3, metrics
from .config import Target
from .structure import (best_chain, ca_coords, heavy_atoms, load_structure, mean_bfactor_ca,
                        read_fasta, write_mapped)


def _prepared(path: Path, seq: str, eu: tuple[int, int], out_pdb: Path, chain: str = ""):
    mapped = best_chain(load_structure(path), seq, chain)
    in_eu = {i: r for i, r in mapped.residues.items() if eu[0] <= i <= eu[1]}
    write_mapped(in_eu, out_pdb)
    return mapped, in_eu


def evaluate_model(model_res: dict, native_res: dict, model_pdb: Path, native_pdb: Path) -> dict:
    common = sorted(set(model_res) & set(native_res))
    n_ref = len(native_res)
    x = ca_coords(model_res, common)
    y = ca_coords(native_res, common)

    tm, (r, t) = metrics.tm_score(x, y, n_ref)
    gdt = metrics.gdt(x, y, n_ref)
    lddt_all, lddt_res = metrics.lddt(heavy_atoms(model_res, common),
                                      heavy_atoms(native_res, sorted(native_res)))
    ca_m = {(i, "CA"): c for i, c in zip(common, x)}
    ca_n = {(i, "CA"): native_res[i]["CA"].coord.astype(float) for i in sorted(native_res)}
    lddt_ca, _ = metrics.lddt(ca_m, ca_n)
    dist = np.linalg.norm(metrics.superpose(x, r, t) - y, axis=1)

    out = {
        "n_native_eu": n_ref,
        "n_common": len(common),
        "tm_score": tm,
        "gdt_ts": 100.0 * float(np.mean(list(gdt.values()))),
        "gdt": {str(k): v for k, v in gdt.items()},
        "lddt": lddt_all,
        "lddt_ca": lddt_ca,
        "rmsd": metrics.rmsd(x, y),
        "per_residue": {
            "index": [int(i) for i in common],
            "ca_distance": [round(float(d), 3) for d in dist],
            "lddt": [round(lddt_res.get(i, float("nan")), 4) for i in common],
        },
    }
    ext = metrics.tmscore_binary(model_pdb, native_pdb)
    if ext:
        out["tmscore_program"] = ext
    return out


def run(target: Target) -> dict:
    out = target.result_dir / "agent2"
    out.mkdir(parents=True, exist_ok=True)
    log = lambda msg: print(f"[agent2 {target.id}] {msg}")  # noqa: E731

    _, seq = read_fasta(target.fasta)
    native_path = target.native_path()
    native_pdb = out / "native_eu.pdb"
    native_map, native_res = _prepared(native_path, seq, target.eu, native_pdb, target.chain)
    log(f"native {native_path.name} chain {native_map.chain_id}: {len(native_res)} residues in "
        f"EU {target.eu[0]}-{target.eu[1]} (seq identity to target {native_map.identity:.1%})")

    results = {"target": target.id, "difficulty": target.difficulty, "eu": list(target.eu),
               "native": {"file": native_path.name, "chain": native_map.chain_id,
                          "identity_to_target": native_map.identity,
                          "residues_in_eu": len(native_res)},
               "methods": {}}

    candidates = {}
    modeller_pdb = target.result_dir / "agent1" / "final_model.pdb"
    if modeller_pdb.exists():
        candidates["MODELLER"] = (modeller_pdb, {})
    else:
        log("no MODELLER model (run agent1 first)")
    top = af3.top_model(target.af3_dir)
    if top:
        candidates["AlphaFold3"] = (top["path"], {k: v for k, v in top.items() if k != "path"})
    else:
        log(f"no AlphaFold3 model in {target.af3_dir}")

    for method, (path, extra) in candidates.items():
        tag = method.lower()
        model_pdb = out / f"{tag}_eu.pdb"
        model_map, model_res = _prepared(path, seq, target.eu, model_pdb)
        res = evaluate_model(model_res, native_res, model_pdb, native_pdb)
        res["file"] = str(path)
        res["mean_ca_bfactor"] = mean_bfactor_ca(model_res, sorted(model_res))  # pLDDT for AF3
        res.update(extra)
        results["methods"][method] = res
        log(f"{method}: TM {res['tm_score']:.3f}  GDT-TS {res['gdt_ts']:.1f}  "
            f"lDDT {res['lddt']:.3f}  RMSD {res['rmsd']:.2f} A")

    (out / "metrics.json").write_text(json.dumps(results, indent=2, default=str))
    return results


# ------------------------------------------------------------------ Claude agent

SYSTEM = """\
You are Agent 2 of a CASP15 benchmark: evaluate a MODELLER template-based model (and an \
AlphaFold3 model when available) against the experimental structure over the CASP \
evaluation unit (EU), and explain the result.

Work through the tools: compute the scores, look at where the errors are, relate them to \
what Agent 1 did (template, alignment coverage, identity), and check that the numbers are \
consistent (e.g. our TM-score vs the TMscore program, residues compared vs EU size). Then \
call finish with an analysis a reader can verify: the scores, which regions are accurate \
or wrong and why (template-covered vs not, loops, termini), how MODELLER compares with \
AlphaFold3, and any caveats. Cite numbers from the tool outputs only; do not guess."""


def _segments(idx: list[int], values: list[float], threshold: float) -> list[dict]:
    from .modeller_build import spans
    bad = [i for i, v in zip(idx, values) if v > threshold]
    by_i = dict(zip(idx, values))
    return [{"residues": f"{s}-{e}", "length": e - s + 1,
             "mean_ca_deviation": round(float(np.mean([by_i[i] for i in range(s, e + 1)
                                                       if i in by_i])), 2)}
            for s, e in spans(bad)]


def run_agent(target: Target) -> dict:
    from . import claude_agent
    from .claude_agent import Finished, Tool
    from .modeller_build import covered_residues, spans
    from .visualize import make_target_figures

    claude_agent.require()
    out = target.result_dir / "agent2"
    out.mkdir(parents=True, exist_ok=True)
    a1 = target.result_dir / "agent1"
    state: dict = {}

    def evaluate_models():
        res = run(target)
        figs = make_target_figures(target)
        state["metrics"] = res
        summary = {"native": res["native"], "eu": res["eu"], "figures": [p.name for p in figs],
                   "methods": {}}
        for m, r in res["methods"].items():
            summary["methods"][m] = {k: r.get(k) for k in (
                "tm_score", "gdt_ts", "gdt", "lddt", "lddt_ca", "rmsd", "n_common",
                "n_native_eu", "tmscore_program", "mean_ca_bfactor", "ranking_score", "ptm")
                if r.get(k) is not None}
        if not res["methods"]:
            summary["note"] = "no models to evaluate"
        return summary

    def per_residue_errors(method: str, ca_threshold: float):
        if "metrics" not in state:
            raise ValueError("call evaluate_models first")
        r = state["metrics"]["methods"].get(method)
        if r is None:
            raise ValueError(f"no {method} model; available: {list(state['metrics']['methods'])}")
        pr = r["per_residue"]
        idx, dev, ld = pr["index"], pr["ca_distance"], pr["lddt"]
        ali = a1 / "alignment.ali"
        cov = set(covered_residues(ali, target.id)) if ali.exists() else set()

        def stats(sel):
            d = [dev[k] for k in sel]
            l_ = [ld[k] for k in sel if ld[k] == ld[k]]
            return {"n": len(sel),
                    "mean_ca_deviation": round(float(np.mean(d)), 2) if d else None,
                    "fraction_within_2A": round(float(np.mean([x <= 2 for x in d])), 3) if d else None,
                    "mean_lddt": round(float(np.mean(l_)), 3) if l_ else None}

        inside = [k for k, i in enumerate(idx) if i in cov]
        outside = [k for k, i in enumerate(idx) if i not in cov]
        worst = sorted(range(len(idx)), key=lambda k: -dev[k])[:10]
        return {
            "method": method,
            "all_compared_residues": stats(range(len(idx))),
            "template_covered_residues": stats(inside),
            "residues_not_covered_by_template": stats(outside),
            "not_covered_segments_in_eu": spans([idx[k] for k in outside]),
            f"segments_above_{ca_threshold:g}A": _segments(idx, dev, ca_threshold),
            "worst_residues": [{"residue": idx[k], "ca_deviation": dev[k],
                                "lddt": ld[k]} for k in worst],
        }

    def get_agent1_decision():
        p = a1 / "decision.json"
        if not p.exists():
            return "Agent 1 has not been run for this target."
        d = json.loads(p.read_text())
        keep = ("mode", "status", "selected_by", "searches", "template", "rationale")
        out_ = {k: d.get(k) for k in keep}
        if "modeller" in d:
            out_["alignment"] = d["modeller"]["alignment"]
            out_["selected_model"] = d["modeller"]["best"]
        return out_

    def finish(analysis_markdown: str):
        (out / "analysis.md").write_text(
            f"# Agent 2 analysis: {target.id} ({target.difficulty})\n\n"
            f"Written by Claude from the tool outputs; full trace in `agent_transcript.md`.\n\n"
            f"{analysis_markdown.strip()}\n")
        raise Finished(analysis_markdown)

    tools = [
        Tool("evaluate_models",
             "Map the MODELLER and AlphaFold3 models and the experimental structure onto "
             "target numbering, trim to the EU, and compute TM-score, GDT-TS, lDDT and CA "
             "RMSD (plus the TMscore program as a cross-check). Writes metrics.json and figures.",
             {}, evaluate_models),
        Tool("per_residue_errors",
             "Per-residue CA deviation (after optimal TM superposition) and lDDT for one "
             "method, split into residues aligned to the template vs not, with segments above "
             "a CA deviation threshold and the worst residues.",
             {"method": {"type": "string", "enum": ["MODELLER", "AlphaFold3"]},
              "ca_threshold": {"type": "number", "description": "Å, e.g. 4"}},
             per_residue_errors),
        Tool("get_agent1_decision",
             "Agent 1's searches, template choice, rationale and alignment statistics.",
             {}, get_agent1_decision),
        Tool("finish", "Write the analysis and end the run.",
             {"analysis_markdown": {"type": "string"}}, finish),
    ]
    task = (f"Target {target.id}, CASP15 class {target.difficulty}, evaluation unit residues "
            f"{target.eu[0]}-{target.eu[1]}. Evaluate the available models and explain the "
            "results.")
    result = claude_agent.run_agent(f"agent2 {target.id}", SYSTEM, task, tools, out)
    metrics = state.get("metrics") or json.loads((out / "metrics.json").read_text())
    metrics["agent"] = {"model": result.model, "steps": result.steps, "usage": result.usage}
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2, default=str))
    return metrics
