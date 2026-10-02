"""Structure-comparison metrics with a fixed residue correspondence.

TM-score and GDT-TS follow the TM-score program (Zhang & Skolnick 2004): superpositions
are seeded from fragments of decreasing length and refined iteratively, and the best
score over all superpositions is kept. lDDT follows Mariani et al. 2013 (all heavy atoms,
15 A inclusion radius, thresholds 0.5/1/2/4 A, no stereochemistry checks).
If the `TMscore` binary is on PATH its values are recorded alongside for cross-checking.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import numpy as np

GDT_CUTOFFS = (1.0, 2.0, 4.0, 8.0)
LDDT_THRESHOLDS = (0.5, 1.0, 2.0, 4.0)
LDDT_RADIUS = 15.0


def kabsch(p: np.ndarray, q: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Rotation r and translation t minimising |p @ r.T + t - q|."""
    pc, qc = p.mean(axis=0), q.mean(axis=0)
    h = (p - pc).T @ (q - qc)
    u, _, vt = np.linalg.svd(h)
    d = np.sign(np.linalg.det(vt.T @ u.T))
    r = vt.T @ np.diag([1.0, 1.0, d]) @ u.T
    return r, qc - pc @ r.T


def superpose(p: np.ndarray, r: np.ndarray, t: np.ndarray) -> np.ndarray:
    return p @ r.T + t


def rmsd(model: np.ndarray, native: np.ndarray) -> float:
    r, t = kabsch(model, native)
    return float(np.sqrt(((superpose(model, r, t) - native) ** 2).sum(axis=1).mean()))


def tm_d0(n: int) -> float:
    return max(1.24 * (n - 15) ** (1.0 / 3.0) - 1.8, 0.5) if n > 21 else 0.5


def _seeds(n: int):
    """Fragment seeds (start, length) in the spirit of TMscore's search."""
    length = n
    while length >= 4:
        step = max(1, min(length // 2, n // 40))
        for start in range(0, n - length + 1, step):
            yield start, length
        if length == 4:
            break
        length = max(length // 2, 4)


def _best_superposition(model: np.ndarray, native: np.ndarray, objective, cutoff: float,
                        max_iter: int = 20):
    """Maximise objective(distances) over seeded, iteratively refined superpositions."""
    n = len(model)
    best_val, best_rt = -1.0, None
    for start, length in _seeds(n):
        sel = np.arange(start, start + length)
        prev = None
        for _ in range(max_iter):
            if len(sel) < 3:
                break
            r, t = kabsch(model[sel], native[sel])
            d = np.linalg.norm(superpose(model, r, t) - native, axis=1)
            val = objective(d)
            if val > best_val:
                best_val, best_rt = val, (r, t)
            cut = cutoff
            new = np.flatnonzero(d < cut)
            while len(new) < 3 and cut < 20.0:
                cut += 0.5
                new = np.flatnonzero(d < cut)
            if prev is not None and np.array_equal(new, prev):
                break
            prev, sel = new, new
    return best_val, best_rt


def tm_score(model: np.ndarray, native: np.ndarray, n_ref: int | None = None):
    """TM-score normalised by n_ref (native length); returns (score, (r, t))."""
    n_ref = n_ref or len(native)
    d0 = tm_d0(n_ref)
    obj = lambda d: float((1.0 / (1.0 + (d / d0) ** 2)).sum() / n_ref)  # noqa: E731
    d0_search = min(max(d0, 4.5), 8.0)  # as in TMscore
    return _best_superposition(model, native, obj, cutoff=d0_search)


def gdt(model: np.ndarray, native: np.ndarray, n_ref: int | None = None,
        cutoffs=GDT_CUTOFFS) -> dict[float, float]:
    """Max fraction of residues within each cutoff, normalised by n_ref."""
    n_ref = n_ref or len(native)
    out = {}
    for c in cutoffs:
        val, _ = _best_superposition(model, native, lambda d, c=c: float((d < c).sum() / n_ref),
                                     cutoff=c)
        out[c] = val
    return out


def gdt_ts(model: np.ndarray, native: np.ndarray, n_ref: int | None = None) -> float:
    return 100.0 * float(np.mean(list(gdt(model, native, n_ref).values())))


def lddt(model_atoms: dict, native_atoms: dict, radius: float = LDDT_RADIUS,
         thresholds=LDDT_THRESHOLDS) -> tuple[float, dict[int, float]]:
    """Global and per-residue lDDT. Atoms are {(res_index, atom_name): xyz}.
    Native atom pairs from different residues within `radius` are scored; atoms
    missing from the model count as not preserved."""
    keys = list(native_atoms)
    nat = np.array([native_atoms[k] for k in keys])
    res = np.array([k[0] for k in keys])
    present = np.array([k in model_atoms for k in keys])
    mod = np.array([model_atoms.get(k, (np.nan, np.nan, np.nan)) for k in keys], dtype=float)

    n = len(keys)
    res_ids, res_pos = np.unique(res, return_inverse=True)
    per_res_total = np.zeros(len(res_ids))
    per_res_kept = np.zeros(len(res_ids))
    total = kept = 0.0
    chunk = 512
    for s in range(0, n, chunk):
        e = min(s + chunk, n)
        dn = np.linalg.norm(nat[s:e, None, :] - nat[None, :, :], axis=2)
        mask = (dn < radius) & (res[s:e, None] != res[None, :])
        # count each unordered pair once: j > i
        mask &= np.arange(s, e)[:, None] < np.arange(n)[None, :]
        ii, jj = np.nonzero(mask)
        ii = ii + s
        if len(ii) == 0:
            continue
        both = present[ii] & present[jj]
        dm = np.linalg.norm(mod[ii] - mod[jj], axis=1)
        diff = np.abs(dm - dn[ii - s, jj])
        frac = np.zeros(len(ii))
        frac[both] = np.mean([diff[both] < t for t in thresholds], axis=0)
        total += len(ii)
        kept += frac.sum()
        for pos in (res_pos[ii], res_pos[jj]):
            per_res_total += np.bincount(pos, minlength=len(res_ids))
            per_res_kept += np.bincount(pos, weights=frac, minlength=len(res_ids))
    global_score = kept / total if total else float("nan")
    per_res = {int(r): float(k / t) for r, k, t in zip(res_ids, per_res_kept, per_res_total) if t}
    return float(global_score), per_res


# ------------------------------------------------------------------ external TMscore

def tmscore_binary(model_pdb: Path, native_pdb: Path) -> dict | None:
    """Run the TMscore program (residue-number correspondence) if available."""
    exe = shutil.which("TMscore")
    if not exe:
        return None
    out = subprocess.run([exe, str(model_pdb), str(native_pdb)], capture_output=True,
                         text=True).stdout
    vals = {}
    for key, pat in {
        "tm_score": r"TM-score\s*=\s*([\d.]+)",
        "gdt_ts": r"GDT-TS-score\s*=\s*([\d.]+)",
        "rmsd": r"RMSD of\s+the common residues\s*=\s*([\d.]+)",
    }.items():
        m = re.search(pat, out)
        if m:
            vals[key] = float(m.group(1))
    if "gdt_ts" in vals:
        vals["gdt_ts"] *= 100.0
    return vals or None
