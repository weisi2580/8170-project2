"""Agent 1: template-based model building.

INPUT target FASTA -> SEARCH (jackhmmer profile HMM vs pre-cutoff PDB) -> FILTER leakage
+ rank -> ALIGN (target and template through the search profile) -> BUILD (automodel,
several models) -> SELECT.

Two modes:
- agent (default): Claude drives the workflow through tools: it chooses search settings,
  inspects candidates, builds models from one or more templates, and selects the final
  model, explaining each decision (agent_transcript.md).
- baseline (--baseline): fixed rules, no Claude: one search with the configured settings,
  the top-scoring template, the lowest-DOPE model.

In both modes leakage control is enforced by code, and no ground-truth coordinates are read;
the experimental structure only enters in Agent 2.
"""

from __future__ import annotations

import csv
import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from . import claude_agent, template_search, template_select
from .claude_agent import Finished, Tool
from .config import Settings, Target
from .modeller_build import build_models, covered_residues, prepare_template, spans
from .structure import read_fasta, write_fasta

N_SHOWN = 15
MAX_BUILDS = 4


def _write_candidates(path, ranked, excluded) -> None:
    rows = [h.to_row() | {"rank": i + 1} for i, h in enumerate(ranked)]
    rows += [h.to_row() | {"rank": ""} for h in excluded]
    if not rows:
        path.write_text("no hits\n")
        return
    cols = ["rank", "entry_id", "entity_id", "chain", "chains", "description", "identity",
            "coverage", "evalue", "bitscore", "query_beg", "query_end", "subject_beg",
            "subject_end", "resolution", "method", "release_date", "completeness", "score",
            "signals", "excluded"]
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def _search_db(target, settings):
    """Pre-cutoff PDB chains; the target's own entry is removed too (normally it is already
    gone, being released after the cutoff)."""
    cutoff = settings.template_release_cutoff
    gone = cutoff and target.pdb.lower() in template_search.released_after(cutoff)
    return template_search.search_db(cutoff, set() if gone else {target.pdb})


def _search(seq, target, settings, workdir, evalue, inclusion_evalue, iterations):
    hits, info = template_search.search(seq, _search_db(target, settings), workdir, evalue,
                                        inclusion_evalue, iterations,
                                        settings.identity_cutoff, settings.max_hits)
    template_select.apply_leakage_filter(hits, target.pdb, settings.template_release_cutoff)
    excluded = [h for h in hits if h.excluded]
    ranked = template_select.rank(hits, settings.rank_weights, settings.n_detailed)
    return hits, ranked, excluded, info


def _search_record(hits, ranked, excluded, info, evalue, inclusion_evalue, iterations) -> dict:
    return {"method": "jackhmmer", "iterations": iterations,
            "inclusion_evalue": inclusion_evalue, "evalue_cutoff": evalue,
            "rounds_run": info["rounds"], "converged": info["converged"],
            "masked_tags": info["masked_tags"], "n_hits": len(hits),
            "n_excluded": len(excluded), "n_eligible": len(ranked)}


def _build(target, seq, hit, chain, workdir, n_models, profile_hmm) -> dict:
    workdir.mkdir(parents=True, exist_ok=True)
    cif = template_search.download_cif(hit.entry_id)
    code = f"{hit.entry_id.lower()}{chain}"
    tpl = prepare_template(cif, chain, workdir, code)
    built = build_models(target.id, seq, tpl, code, workdir, Path(profile_hmm), n_models)
    built["template_pdb"] = str(tpl)
    return built


def _base_decision(target, seq, settings, n_models) -> dict:
    return {
        "target": target.id,
        "difficulty": target.difficulty,
        "sequence_length": len(seq),
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "settings": {
            "template_release_cutoff": settings.template_release_cutoff,
            "rank_weights": settings.rank_weights,
            "n_models": n_models,
        },
    }


def _install_final(out, built: dict, model_name: str) -> None:
    work = Path(built["alignment_file"]).parent
    shutil.copy(work / model_name, out / "final_model.pdb")
    shutil.copy(built["alignment_file"], out / "alignment.ali")
    shutil.copy(built["template_pdb"], out / "template.pdb")


def _models_table(built: dict, selected: str) -> list[str]:
    md = ["| model | DOPE | z-DOPE | GA341 | molpdf |", "|---|---|---|---|---|"]
    for m in built["models"]:
        if "dope" not in m:
            md.append(f"| {m['name']} | failed: {m['failure']} | | | |")
            continue
        star = " (selected)" if m["name"] == selected else ""
        z = f"{m['zdope']:.2f}" if m.get("zdope") is not None else "–"
        md.append(f"| {m['name']}{star} | {m['dope']:.1f} | {z} | {m['ga341']:.3f} "
                  f"| {m['molpdf']:.1f} |")
    a = built["alignment"]
    md += ["", f"alignment: {a['aligned_residues']} aligned residues, identity "
               f"{a['identity']:.1%}, target coverage {a['coverage']:.1%}"]
    return md


def run(target: Target, settings: Settings, n_models: int | None = None,
        search_only: bool = False, template: str | None = None) -> dict:
    if claude_agent.baseline_mode():
        return run_baseline(target, settings, n_models, search_only, template)
    if search_only or template:
        raise SystemExit("--search-only and --template are for --baseline runs; "
                         "in agent mode Claude makes these choices")
    return run_agent(target, settings, n_models)


# ------------------------------------------------------------------ baseline (no Claude)

def run_baseline(target: Target, settings: Settings, n_models: int | None = None,
                 search_only: bool = False, template: str | None = None) -> dict:
    out = target.result_dir / "agent1"
    out.mkdir(parents=True, exist_ok=True)
    log = lambda msg: print(f"[agent1 {target.id} baseline] {msg}")  # noqa: E731

    _, seq = read_fasta(target.fasta)
    if len(seq) != target.length:
        log(f"warning: FASTA has {len(seq)} residues, config says {target.length}")
    write_fasta(out / "target.fasta", target.id, seq)

    ev, inc, it = settings.evalue_cutoff, settings.inclusion_evalue, settings.search_iterations
    log(f"jackhmmer: {it} round(s), profile inclusion E <= {inc:g}, report E <= {ev:g}")
    hits, ranked, excluded, info = _search(seq, target, settings, out / "search", ev, inc, it)
    if template:  # manual override, e.g. "1ABC:A"
        entry, _, chain = template.upper().partition(":")
        forced = [h for h in ranked if h.entry_id == entry and (not chain or chain in h.chains)]
        if not forced:
            raise SystemExit(f"template {template} is not among the eligible hits")
        if chain:
            forced[0].chain = chain
        ranked.remove(forced[0])
        ranked.insert(0, forced[0])
    _write_candidates(out / "candidates.csv", ranked, excluded)
    log(f"{len(hits)} hit(s), {len(excluded)} excluded by leakage control, "
        f"{len(ranked)} eligible")

    n = n_models or settings.n_models
    decision = _base_decision(target, seq, settings, n) | {
        "mode": "baseline",
        "selected_by": "user" if template else "score",
        "searches": [_search_record(hits, ranked, excluded, info, ev, inc, it)],
    }

    if not ranked:
        decision["status"] = "no_template"
        decision["rationale"] = (
            "No eligible template survived the search and leakage filter. Consider more "
            "search iterations or a looser inclusion E-value.")
        (out / "decision.json").write_text(json.dumps(decision, indent=2))
        (out / "decision.md").write_text(f"# {target.id}: no template\n\n{decision['rationale']}\n")
        log(decision["rationale"])
        return decision

    best = ranked[0]
    rationale = template_select.explain(best, ranked, len(excluded))
    decision["template"] = best.to_row()
    decision["rationale"] = rationale
    log(rationale.splitlines()[0])

    md = [f"# Agent 1 decision log: {target.id} ({target.difficulty}), baseline", "",
          f"- hits: {len(hits)}, excluded by leakage control: {len(excluded)}, "
          f"eligible: {len(ranked)}", f"- selected by: {decision['selected_by']}", "",
          "## Template choice", "", rationale, ""]
    if search_only:
        decision["status"] = "template_selected"
    else:
        log(f"building {n} model(s) with MODELLER on template {best.entry_id}:{best.chain}")
        built = _build(target, seq, best, best.chain, out / "modeller", n, info["profile"])
        _install_final(out, built, built["best"]["name"])
        decision |= {"modeller": built, "final_model": "agent1/final_model.pdb",
                     "status": "modeled"}
        log(f"lowest DOPE: {built['best']['name']} ({built['best']['dope']:.1f})")
        md += ["## MODELLER models", "", *_models_table(built, built["best"]["name"])]

    (out / "decision.json").write_text(json.dumps(decision, indent=2, default=str))
    (out / "decision.md").write_text("\n".join(md) + "\n")
    return decision


# ------------------------------------------------------------------ Claude agent

SYSTEM = """\
You are Agent 1 of a CASP15 benchmark: build the best possible template-based model of a \
target protein with MODELLER, using only the target sequence and structures in the PDB. \
Your model will later be compared with the experimental structure over the CASP \
evaluation unit (EU), so what matters is how accurately the EU residues are modeled.

You work through tools. The search is an iterative profile HMM search (HMMER jackhmmer) \
against PDB chains released before the CASP15 season: round 1 compares the sequence, later \
rounds search with a profile built from the hits so far, which finds remote homologues. \
Expression tags (His-tags, protease sites) are masked. Candidates are ranked by a \
composite score (identity, coverage, E-value, resolution, completeness); leakage control \
has removed the target's own entry and anything released after the season, and the tools \
refuse excluded entries. You never see the experimental structure, and you must not rely on any \
recollection of this target's real structure: decide from the tool outputs only.

How to work:
- Start with the default search (3 iterations, inclusion E 1e-3). If it yields no usable \
template, try more iterations or a looser inclusion E-value; if hits look unrelated to \
each other, the profile may have drifted, so try a stricter one.
- Read the candidates critically: which target residues does each cover, especially the \
EU? Is a lower-scoring candidate better for the EU (coverage, identity in the covered \
region, completeness, resolution)? Are top hits redundant copies of the same protein?
- Build models from the most promising template; build from an alternative too when the \
choice is genuinely uncertain (at most {max_builds} builds). The target-template alignment \
comes from the search profile. Compare builds by \
alignment coverage of the EU, alignment identity, and normalized DOPE (z-DOPE, lower is \
better, comparable across builds); GA341 near 1 means a reliable fold. Raw DOPE is only \
comparable between models of the same build.
- Finish by calling finalize with the build and model to keep and a rationale that a \
reader can check: the decisive numbers, the alternatives you considered and why you \
rejected them, and the risks (uncovered regions, low identity). If no usable template \
exists after reasonable searching, finalize with build_id null and explain.
""".format(max_builds=MAX_BUILDS)


def _hit_row(i: int, h) -> dict:
    return {
        "rank": i, "entry_id": h.entry_id, "chain": h.chain, "chains": ",".join(h.chains),
        "description": h.description, "identity": round(h.identity, 3),
        "coverage": round(h.coverage, 3), "target_range": f"{h.query_beg}-{h.query_end}",
        "evalue": f"{h.evalue:.1e}", "resolution": h.resolution, "method": h.method,
        "released": h.release_date,
        "completeness": None if h.completeness is None else round(h.completeness, 3),
        "score": round(h.score, 3),
    }


def run_agent(target: Target, settings: Settings, n_models: int | None = None) -> dict:
    claude_agent.require()
    out = target.result_dir / "agent1"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    _, seq = read_fasta(target.fasta)
    write_fasta(out / "target.fasta", target.id, seq)
    default_n = n_models or settings.n_models
    searches: dict[str, dict] = {}
    builds: dict[str, dict] = {}

    def search_templates(iterations: int, inclusion_evalue: float, evalue_cutoff: float):
        it = max(1, min(int(iterations), 6))
        sid = f"N{it}_inc{inclusion_evalue:g}_E{evalue_cutoff:g}"
        if sid not in searches:
            hits, ranked, excluded, info = _search(seq, target, settings,
                                                   out / "searches" / sid, evalue_cutoff,
                                                   inclusion_evalue, it)
            _write_candidates(out / f"candidates_{sid}.csv", ranked, excluded)
            searches[sid] = _search_record(hits, ranked, excluded, info, evalue_cutoff,
                                           inclusion_evalue, it) | {
                "ranked": ranked, "excluded": excluded, "profile": info["profile"]}
        s = searches[sid]
        reasons = Counter(h.excluded.split(",")[0] for h in s["excluded"])
        return {
            "search_id": sid, "rounds_run": s["rounds_run"], "converged": s["converged"],
            "masked_tags": s["masked_tags"],
            "n_hits": s["n_hits"], "n_excluded": len(s["excluded"]),
            "excluded_reasons": dict(reasons), "n_eligible": len(s["ranked"]),
            "note": (f"completeness is measured for the top {settings.n_detailed} only"
                     if s["ranked"] else "no eligible templates"),
            "candidates": [_hit_row(i + 1, h) for i, h in enumerate(s["ranked"][:N_SHOWN])],
        }

    def show_candidates(search_id: str, offset: int):
        if search_id not in searches:
            raise ValueError(f"unknown search_id {search_id}; run search_templates first")
        ranked = searches[search_id]["ranked"]
        return [_hit_row(i + 1, h) for i, h in enumerate(ranked) if offset <= i < offset + 20]

    def build_model(search_id: str, entry_id: str, chain: str, n_models: int):
        if search_id not in searches:
            raise ValueError(f"unknown search_id {search_id}")
        if len(builds) >= MAX_BUILDS:
            raise ValueError(f"build limit ({MAX_BUILDS}) reached; finalize with an existing build")
        entry = entry_id.upper()
        s = searches[search_id]
        bad = [h for h in s["excluded"] if h.entry_id == entry]
        if bad:
            raise ValueError(f"{entry} is excluded by leakage control: {bad[0].excluded}")
        match = [h for h in s["ranked"] if h.entry_id == entry and chain in h.chains]
        if not match:
            raise ValueError(f"{entry}:{chain} is not an eligible candidate of {search_id}")
        bid = f"{entry}{chain}"
        if bid in builds:
            if builds[bid]["search_id"] == search_id:
                raise ValueError(f"build {bid} already exists")
            bid = f"{entry}{chain}_{search_id}"  # same template, other search's alignment
            if bid in builds:
                raise ValueError(f"build {bid} already exists")
        n = max(1, min(int(n_models), 10))
        print(f"[agent1 {target.id}] MODELLER: {n} model(s) on {entry}:{chain}")
        built = _build(target, seq, match[0], chain, out / "builds" / bid, n, s["profile"])
        cov = covered_residues(built["alignment_file"], target.id)
        eu = set(range(target.eu[0], target.eu[1] + 1))
        uncovered = [i for i in sorted(eu) if i not in set(cov)]
        builds[bid] = {"hit": match[0], "chain": chain, "built": built, "search_id": search_id}
        return {
            "build_id": bid, "template": f"{entry}:{chain}",
            "alignment": built["alignment"],
            "template_covered_target_segments": spans(cov),
            "eu": list(target.eu),
            "eu_fraction_covered": round(1 - len(uncovered) / len(eu), 3),
            "eu_uncovered_segments": spans(uncovered),
            "models": [{k: (round(v, 3) if isinstance(v, float) else v)
                        for k, v in m.items()} for m in built["models"]],
            "lowest_dope_model": built["best"]["name"],
        }

    def finalize(build_id: str | None, model_name: str | None, rationale: str):
        decision = _base_decision(target, seq, settings, default_n) | {
            "mode": "agent", "selected_by": "claude",
            "searches": [{k: v for k, v in s.items()
                          if k not in ("ranked", "excluded", "profile")}
                         for s in searches.values()],
            "builds": {bid: {"template": f"{b['hit'].entry_id}:{b['chain']}",
                             "alignment": b["built"]["alignment"],
                             "models": b["built"]["models"]} for bid, b in builds.items()},
            "rationale": rationale,
        }
        md = [f"# Agent 1 decision log: {target.id} ({target.difficulty})", "",
              "Decisions made by Claude through tool calls; full reasoning in "
              "`agent_transcript.md`.", "", "## Searches", ""]
        for s in decision["searches"]:
            md.append(f"- jackhmmer, {s['iterations']} round(s) ({s['rounds_run']} run"
                      f"{', converged' if s['converged'] else ''}), inclusion E ≤ "
                      f"{s['inclusion_evalue']:g}, report E ≤ {s['evalue_cutoff']:g}: "
                      f"{s['n_hits']} hits, {s['n_excluded']} excluded by leakage control, "
                      f"{s['n_eligible']} eligible")
        if build_id is None:
            decision["status"] = "no_template"
            md += ["", "## Decision: no template", "", rationale]
        else:
            if build_id not in builds:
                raise ValueError(f"unknown build_id {build_id}; built: {list(builds)}")
            b = builds[build_id]
            built = b["built"]
            name = model_name or built["best"]["name"]
            chosen = next((m for m in built["models"] if m["name"] == name and "dope" in m), None)
            if chosen is None:
                raise ValueError(f"{name} is not a successful model of build {build_id}")
            _install_final(out, built, name)
            hit = b["hit"]
            hit.chain = b["chain"]
            decision |= {"status": "modeled", "template": hit.to_row(),
                         "modeller": built | {"best": chosen},
                         "final_model": "agent1/final_model.pdb"}
            md += ["", f"## Decision: template {hit.entry_id}:{b['chain']}, model {name}", "",
                   rationale, ""]
            for bid, bb in builds.items():
                md += [f"### Build {bid}" + (" (selected)" if bid == build_id else ""), "",
                       *_models_table(bb["built"], name if bid == build_id else ""), ""]
        (out / "decision.json").write_text(json.dumps(decision, indent=2, default=str))
        (out / "decision.md").write_text("\n".join(md) + "\n")
        raise Finished(decision)

    tools = [
        Tool("search_templates",
             "Iterative profile HMM search (jackhmmer) of the target against pre-cutoff PDB "
             "chains. Leakage control is applied. Returns rounds run, whether the profile "
             "converged, masked tags, counts and the top candidates by composite score. "
             "Takes about a minute.",
             {"iterations": {"type": "integer", "description": "rounds, 1-6; default 3"},
              "inclusion_evalue": {"type": "number",
                                   "description": "E-value for a hit to enter the profile; "
                                                  "default 1e-3"},
              "evalue_cutoff": {"type": "number",
                                "description": "report hits up to this E-value; default 1"}},
             search_templates),
        Tool("show_candidates", "Show 20 more ranked candidates of a search from offset (0-based).",
             {"search_id": {"type": "string"}, "offset": {"type": "integer"}}, show_candidates),
        Tool("build_model",
             "Align the target to one template chain through the search profile and build "
             "n_models MODELLER models (automodel). Returns alignment statistics, which target/EU residues the "
             "template covers, and DOPE, normalized DOPE (z-DOPE), GA341, molpdf per model. "
             "Takes about a minute.",
             {"search_id": {"type": "string"}, "entry_id": {"type": "string"},
              "chain": {"type": "string"},
              "n_models": {"type": "integer", "description": f"1-10, default {default_n}"}},
             build_model),
        Tool("finalize",
             "Record the final choice and end the run. build_id null means no usable template. "
             "model_name null keeps the build's lowest-DOPE model.",
             {"build_id": {"type": ["string", "null"]},
              "model_name": {"type": ["string", "null"]},
              "rationale": {"type": "string",
                            "description": "Markdown: decision, decisive numbers, "
                                           "alternatives rejected, risks"}},
             finalize),
    ]
    task = (f"Target {target.id}, CASP15 class {target.difficulty}, {len(seq)} residues. "
            f"Evaluation unit: residues {target.eu[0]}-{target.eu[1]}. "
            f"Default number of models per build: {default_n}.\n\nSequence:\n{seq}")
    run = claude_agent.run_agent(f"agent1 {target.id}", SYSTEM, task, tools, out)
    decision = run.result
    decision["agent"] = {"model": run.model, "steps": run.steps, "usage": run.usage}
    (out / "decision.json").write_text(json.dumps(decision, indent=2, default=str))
    return decision

