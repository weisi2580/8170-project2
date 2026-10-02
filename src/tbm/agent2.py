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
