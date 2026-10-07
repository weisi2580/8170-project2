"""3D overlays rendered headless with PyMOL (conda-forge `pymol-open-source`).

Each model is placed on the experimental structure with the same TM-score superposition
Agent 2 scores with, so the picture shows what the TM-score rewards: the part of the model
that fits. Native in grey, MODELLER in blue, AlphaFold3 in orange.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from . import metrics
from .config import Target
from .structure import ca_coords, load_structure
from .visualize import COLORS

WIDTH, HEIGHT = 2400, 2000


def available() -> bool:
    try:
        import pymol  # noqa: F401
    except ImportError:
        return False
    return True


def _residues(pdb: Path) -> dict:
    chain = next(load_structure(pdb)[0].get_chains())
    return {r.id[1]: r for r in chain if "CA" in r}


def _tm_matrix(model_pdb: Path, native_pdb: Path) -> list[float]:
    """4x4 row-major matrix moving the model onto the native (TM-score superposition)."""
    m, n = _residues(model_pdb), _residues(native_pdb)
    common = sorted(set(m) & set(n))
    _, (r, t) = metrics.tm_score(ca_coords(m, common), ca_coords(n, common), len(n))
    mat = np.eye(4)
    mat[:3, :3], mat[:3, 3] = r, t
    return [float(v) for v in mat.ravel()]


def _trim(png: Path, pad: int = 24) -> None:
    """Crop the white margin PyMOL leaves around the molecules."""
    from PIL import Image, ImageChops
    img = Image.open(png).convert("RGB")
    box = ImageChops.difference(img, Image.new("RGB", img.size, "white")).getbbox()
    if box:
        l, t, r, b = box
        img.crop((max(l - pad, 0), max(t - pad, 0), min(r + pad, img.width),
                  min(b + pad, img.height))).save(png)


def _cmd():
    import pymol
    from pymol import cmd
    pymol.finish_launching(["pymol", "-cq"])
    return cmd


def render_target(target: Target) -> list[Path]:
    """Writes <id>_3d_MODELLER.png and <id>_3d_AlphaFold3.png next to Agent 2's outputs."""
    a2 = target.result_dir / "agent2"
    native = a2 / "native_eu.pdb"
    if not native.exists():
        return []
    cmd = _cmd()
    outs = []
    for method, fname in (("MODELLER", "modeller_eu.pdb"), ("AlphaFold3", "alphafold3_eu.pdb")):
        model = a2 / fname
        if not model.exists():
            continue
        cmd.reinitialize()
        cmd.bg_color("white")
        cmd.set("ray_opaque_background", 1)
        cmd.set("cartoon_transparency", 0)
        cmd.set("ray_trace_mode", 1)
        cmd.set("ray_trace_color", "0x52514e")
        cmd.set("antialias", 2)
        cmd.set("cartoon_fancy_helices", 1)
        cmd.set("depth_cue", 0)
        cmd.load(str(native), "native")
        cmd.load(str(model), "pred")
        cmd.transform_selection("pred", _tm_matrix(model, native), homogenous=1)
        cmd.hide("everything")
        cmd.show("cartoon")
        for obj, color in (("native", COLORS["native"]), ("pred", COLORS[method])):
            name = f"c_{obj}"
            cmd.set_color(name, [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)])
            cmd.color(name, obj)
        cmd.orient("native")
        cmd.zoom("native or pred", 1, complete=1)
        out = a2 / f"{target.id}_3d_{method}.png"
        cmd.png(str(out), width=WIDTH, height=HEIGHT, dpi=200, ray=1)
        _trim(out)
        outs.append(out)
    return outs
