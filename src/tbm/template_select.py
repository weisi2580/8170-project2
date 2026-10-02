"""Leakage filtering and template ranking for Agent 1."""

from __future__ import annotations

import math
from pathlib import Path

from Bio.PDB.MMCIF2Dict import MMCIF2Dict

from .template_search import Hit, download_cif

# Resolution mapped to 0..1: <=1.5 A -> 1, >=4 A -> 0 (NMR / unknown -> 0.3).
RES_BEST, RES_WORST, RES_UNKNOWN = 1.5, 4.0, 0.3


def apply_leakage_filter(hits: list[Hit], target_pdb: str, release_cutoff: str) -> None:
    """Mark hits that must not be used as templates. Excluded hits stay in the log."""
    for h in hits:
        if h.entry_id.upper() == target_pdb.upper():
            h.excluded = "target's own experimental structure"
        elif release_cutoff and h.release_date and h.release_date > release_cutoff:
            h.excluded = f"released {h.release_date}, after cutoff {release_cutoff}"
        elif h.entity_id.endswith("?"):
            h.excluded = "could not resolve polymer entity"


def observed_flags(cif: Path, chain: str) -> dict[int, bool]:
    """{seq_id: has coordinates} for an author chain, from _pdbx_poly_seq_scheme."""
    d = MMCIF2Dict(str(cif))
    strands = d.get("_pdbx_poly_seq_scheme.pdb_strand_id", [])
    seq_ids = d.get("_pdbx_poly_seq_scheme.seq_id", [])
    auth = d.get("_pdbx_poly_seq_scheme.auth_seq_num", [])
    return {int(s): a not in ("?", ".") for c, s, a in zip(strands, seq_ids, auth) if c == chain}


def completeness(hit: Hit, cif: Path) -> tuple[float, str]:
    """Best fraction of observed residues within the aligned template region, and its chain."""
    best = (0.0, hit.chains[0] if hit.chains else "")
    span = range(hit.subject_beg, hit.subject_end + 1)
    for chain in hit.chains:
        flags = observed_flags(cif, chain)
        if not flags:
            continue
        frac = sum(flags.get(i, False) for i in span) / len(span)
        if frac > best[0]:
            best = (frac, chain)
    return best


def signals(hit: Hit) -> dict[str, float]:
    ev = max(hit.evalue, 1e-300)
    # -log10(E): 0 at E>=1, saturates at 1 for E<=1e-50
    e_sig = min(max(-math.log10(ev), 0.0), 50.0) / 50.0
    if hit.resolution is None:
        r_sig = RES_UNKNOWN
    else:
        r_sig = min(max((RES_WORST - hit.resolution) / (RES_WORST - RES_BEST), 0.0), 1.0)
    return {
        "identity": hit.identity,
        "coverage": hit.coverage,
        "evalue": e_sig,
        "resolution": r_sig,
        "completeness": hit.completeness if hit.completeness is not None else 0.5,
    }


def score(hit: Hit, weights: dict[str, float]) -> float:
    hit.signals = signals(hit)
    total = sum(weights.values())
    hit.score = sum(weights[k] * hit.signals[k] for k in weights) / total
    return hit.score


def rank(hits: list[Hit], weights: dict[str, float], n_detailed: int,
         check_completeness: bool = True) -> list[Hit]:
    """Score eligible hits; download the top n to measure missing residues; re-rank."""
    eligible = [h for h in hits if not h.excluded]
    for h in eligible:
        score(h, weights)
    eligible.sort(key=lambda h: h.score, reverse=True)
    if check_completeness:
        for h in eligible[:n_detailed]:
            cif = download_cif(h.entry_id)
            h.completeness, h.chain = completeness(h, cif)
            score(h, weights)
    for h in eligible:
        if not h.chain and h.chains:
            h.chain = h.chains[0]
    # Only fully characterised candidates compete for first place.
    detailed = sorted(eligible[:n_detailed], key=lambda h: h.score, reverse=True)
    return detailed + eligible[n_detailed:]


def explain(selected: Hit, ranked: list[Hit], n_excluded: int) -> str:
    """Plain-language rationale recorded alongside the decision."""
    lines = [
        f"Selected template {selected.entry_id} chain {selected.chain} "
        f"({selected.description or 'no description'}).",
        f"- sequence identity {selected.identity:.1%} over the aligned region, "
        f"target coverage {selected.coverage:.1%} "
        f"(target residues {selected.query_beg}-{selected.query_end}), E-value {selected.evalue:.2e}",
        f"- {selected.method or 'unknown method'}, resolution "
        + (f"{selected.resolution:.2f} A" if selected.resolution else "n/a")
        + f", released {selected.release_date or 'n/a'}",
    ]
    if selected.completeness is not None:
        lines.append(f"- {selected.completeness:.1%} of the aligned template residues have coordinates")
    lines.append(f"- composite score {selected.score:.3f} (weights: identity, coverage, "
                 f"E-value, resolution, completeness)")
    runners = [h for h in ranked[1:4]]
    if runners:
        lines.append("Runner-up candidates:")
        for h in runners:
            lines.append(f"  - {h.entry_id}:{h.chain} score {h.score:.3f}, id {h.identity:.1%}, "
                         f"cov {h.coverage:.1%}, E {h.evalue:.1e}")
    lines.append(f"{n_excluded} hit(s) were excluded by leakage control (see candidates.csv).")
    return "\n".join(lines)
