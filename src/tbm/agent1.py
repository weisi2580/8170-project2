"""Agent 1: template-based model building.

INPUT target FASTA -> SEARCH RCSB (MMseqs2) -> FILTER leakage + rank -> ALIGN (align2d)
-> BUILD (automodel, several models) -> SELECT lowest DOPE.
No ground-truth coordinates are read here; the experimental structure only enters in Agent 2.
"""

from __future__ import annotations

import csv
import json
import shutil
from datetime import datetime, timezone

from . import template_search, template_select
from .config import Settings, Target
from .modeller_build import build_models, prepare_template
from .structure import read_fasta, write_fasta


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


def run(target: Target, settings: Settings, n_models: int | None = None,
        search_only: bool = False, template: str | None = None) -> dict:
    out = target.result_dir / "agent1"
    out.mkdir(parents=True, exist_ok=True)
    log = lambda msg: print(f"[agent1 {target.id}] {msg}")  # noqa: E731

    _, seq = read_fasta(target.fasta)
    if len(seq) != target.length:
        log(f"warning: FASTA has {len(seq)} residues, config says {target.length}")
    write_fasta(out / "target.fasta", target.id, seq)

    log(f"searching PDB ({settings.search_backend}, E <= {settings.evalue_cutoff})")
    hits = template_search.search(seq, settings.search_backend, settings.evalue_cutoff,
                                  settings.identity_cutoff, settings.max_hits)
    log(f"{len(hits)} hit(s)")

    template_select.apply_leakage_filter(hits, target.pdb, settings.template_release_cutoff)
    excluded = [h for h in hits if h.excluded]
    ranked = template_select.rank(hits, settings.rank_weights, settings.n_detailed)
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
    log(f"{len(excluded)} excluded by leakage control, {len(ranked)} eligible")

    decision = {
        "target": target.id,
        "difficulty": target.difficulty,
        "sequence_length": len(seq),
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "settings": {
            "search_backend": settings.search_backend,
            "evalue_cutoff": settings.evalue_cutoff,
            "template_release_cutoff": settings.template_release_cutoff,
            "rank_weights": settings.rank_weights,
            "n_models": n_models or settings.n_models,
        },
        "n_hits": len(hits),
        "n_excluded": len(excluded),
        "n_eligible": len(ranked),
    }

    if not ranked:
        decision["status"] = "no_template"
        decision["rationale"] = (
            "No eligible template survived the search and leakage filter. Consider "
            "search_backend='local' (more sensitive MMseqs2) or a higher evalue_cutoff.")
        (out / "decision.json").write_text(json.dumps(decision, indent=2))
        (out / "decision.md").write_text(f"# {target.id}: no template\n\n{decision['rationale']}\n")
        log(decision["rationale"])
        return decision

    best = ranked[0]
    rationale = template_select.explain(best, ranked, len(excluded))
    decision["template"] = best.to_row()
    decision["rationale"] = rationale
    log(rationale.splitlines()[0])

    if not search_only:
        work = out / "modeller"
        work.mkdir(exist_ok=True)
        cif = template_search.download_cif(best.entry_id)
        code = f"{best.entry_id.lower()}{best.chain}"
        tpl = prepare_template(cif, best.chain, work, code)
        shutil.copy(tpl, out / "template.pdb")
        n = n_models or settings.n_models
        log(f"building {n} model(s) with MODELLER on template {code}")
        built = build_models(target.id, seq, tpl, code, work, n, settings.max_gap_length)
        shutil.copy(work / built["best"]["name"], out / "final_model.pdb")
        shutil.copy(work / "alignment.ali", out / "alignment.ali")
        decision["modeller"] = built
        decision["final_model"] = str((out / "final_model.pdb").relative_to(target.result_dir))
        decision["status"] = "modeled"
        log(f"lowest DOPE: {built['best']['name']} ({built['best']['dope']:.1f})")
    else:
        decision["status"] = "template_selected"

    (out / "decision.json").write_text(json.dumps(decision, indent=2, default=str))
    md = [f"# Agent 1 decision log: {target.id} ({target.difficulty})", "",
          f"- hits: {len(hits)}, excluded by leakage control: {len(excluded)}, "
          f"eligible: {len(ranked)}", "", "## Template choice", "", rationale, ""]
    if "modeller" in decision:
        md += ["## MODELLER models", "", "| model | DOPE | GA341 | molpdf |", "|---|---|---|---|"]
        for m in decision["modeller"]["models"]:
            if "dope" in m:
                star = " (selected)" if m["name"] == decision["modeller"]["best"]["name"] else ""
                md.append(f"| {m['name']}{star} | {m['dope']:.1f} | {m['ga341']:.3f} "
                          f"| {m['molpdf']:.1f} |")
            else:
                md.append(f"| {m['name']} | failed: {m['failure']} | | |")
        a = decision["modeller"]["alignment"]
        md += ["", f"align2d: {a['aligned_residues']} aligned residues, identity "
                   f"{a['identity']:.1%}, target coverage {a['coverage']:.1%}"]
    (out / "decision.md").write_text("\n".join(md) + "\n")
    return decision
