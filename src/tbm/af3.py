"""Locate and read AlphaFold3 Server outputs.

Expected layout (unzipped server download, any file prefix):
    data/af3/<TARGET>/fold_<name>_model_0.cif ... _model_4.cif
    data/af3/<TARGET>/fold_<name>_summary_confidences_0.json ...
A zip file in data/af3/<TARGET>/ (or data/af3/<TARGET>.zip) is extracted automatically.
"""

from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path

MODEL_RE = re.compile(r"model_(\d+)\.cif$")


def _extract_zips(af3_dir: Path) -> None:
    zips = list(af3_dir.glob("*.zip"))
    sibling = af3_dir.with_suffix(".zip")
    if sibling.exists():
        zips.append(sibling)
    for z in zips:
        af3_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(z) as zf:
            for member in zf.namelist():
                name = Path(member).name
                if name and (name.endswith(".cif") or name.endswith(".json")):
                    target = af3_dir / name
                    if not target.exists():
                        target.write_bytes(zf.read(member))


def find_models(af3_dir: Path) -> list[dict]:
    """All server models with their summary confidences, best ranking_score first."""
    af3_dir = Path(af3_dir)
    _extract_zips(af3_dir)
    if not af3_dir.exists():
        return []
    models = []
    for cif in sorted(af3_dir.rglob("*model_*.cif")):
        m = MODEL_RE.search(cif.name)
        if not m:
            continue
        idx = int(m.group(1))
        prefix = cif.name[: m.start()]
        conf_path = cif.with_name(f"{prefix}summary_confidences_{idx}.json")
        conf = json.loads(conf_path.read_text()) if conf_path.exists() else {}
        models.append({
            "index": idx,
            "path": cif,
            "ranking_score": conf.get("ranking_score"),
            "ptm": conf.get("ptm"),
            "fraction_disordered": conf.get("fraction_disordered"),
            "has_clash": conf.get("has_clash"),
        })
    # Server ranks model_0 first; fall back to file index when scores are missing.
    models.sort(key=lambda d: (-(d["ranking_score"] if d["ranking_score"] is not None else -1e9),
                               d["index"]))
    return models


def top_model(af3_dir: Path) -> dict | None:
    models = find_models(af3_dir)
    return models[0] if models else None
