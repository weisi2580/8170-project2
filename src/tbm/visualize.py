"""Figures (matplotlib, PyMOL 3D overlays) and ChimeraX scripts for structural comparison."""

from __future__ import annotations

import json
import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from .config import Target  # noqa: E402
from .modeller_build import covered_residues, spans  # noqa: E402

# Fixed identity colors (categorical slots 1-3 of the reference palette).
COLORS = {"MODELLER": "#2a78d6", "AlphaFold3": "#eb6834", "template": "#1baf7a",
          "native": "#9a9a96"}
INK, INK_MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"
METHODS = ("MODELLER", "AlphaFold3")


def _style(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(INK_MUTED)
    ax.tick_params(colors=INK_MUTED, labelsize=8)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def template_covered(target: Target) -> list[int]:
    """Target residues aligned to a template residue in the target-template alignment."""
    ali = target.result_dir / "agent1" / "alignment.ali"
    return covered_residues(ali, target.id) if ali.exists() else []


def per_residue_plot(target: Target, metrics: dict, out: Path) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(9, 5), sharex=True)
    covered = template_covered(target)
    for ax in axes:
        _style(ax)
        for s, e in spans(covered):
            ax.axvspan(s - 0.5, e + 0.5, color=GRID, alpha=0.6, linewidth=0)
    for method in METHODS:
        if method not in metrics["methods"]:
            continue
        pr = metrics["methods"][method]["per_residue"]
        axes[0].plot(pr["index"], pr["ca_distance"], color=COLORS[method], lw=2, label=method)
        axes[1].plot(pr["index"], pr["lddt"], color=COLORS[method], lw=2, label=method)
    axes[0].set_ylabel("CA deviation (Å)", color=INK, fontsize=9)
    axes[1].set_ylabel("per-residue lDDT", color=INK, fontsize=9)
    axes[1].set_ylim(0, 1.02)
    axes[1].set_xlabel("target residue", color=INK, fontsize=9)
    axes[0].legend(frameon=False, fontsize=8, loc="upper right")
    note = " · shaded: residues aligned to the template" if covered else ""
    fig.suptitle(f"{target.id} ({target.difficulty}) — EU {target.eu[0]}–{target.eu[1]}{note}",
                 fontsize=10, color=INK, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(out, dpi=200)
    plt.close(fig)


def summary_plot(rows: list[dict], out: Path) -> None:
    """Small multiples: one panel per metric, targets on x, methods as paired bars."""
    targets = list(dict.fromkeys(r["target"] for r in rows))
    panels = [("tm_score", "TM-score ↑", (0, 1)), ("gdt_ts", "GDT-TS ↑", (0, 100)),
              ("lddt", "lDDT ↑", (0, 1)), ("rmsd", "RMSD (Å) ↓", None)]
    fig, axes = plt.subplots(1, 4, figsize=(12, 3.4))
    width = 0.38
    for ax, (key, title, ylim) in zip(axes, panels):
        _style(ax)
        for k, method in enumerate(METHODS):
            xs, ys = [], []
            for i, t in enumerate(targets):
                r = next((r for r in rows if r["target"] == t and r["method"] == method), None)
                if r is not None:
                    xs.append(i + (k - 0.5) * (width + 0.02))
                    ys.append(r[key])
            if xs:
                ax.bar(xs, ys, width=width, color=COLORS[method], label=method)
        ax.set_xlim(-0.6, len(targets) - 0.4)
        ax.set_xticks(range(len(targets)))
        ax.set_xticklabels(targets, fontsize=8, color=INK)
        ax.set_title(title, fontsize=9, color=INK, loc="left")
        if ylim:
            ax.set_ylim(*ylim)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, frameon=False, fontsize=8, loc="upper center", ncol=2)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    fig.savefig(out, dpi=200)
    plt.close(fig)


def chimerax_script(target: Target, out: Path) -> Path:
    """ChimeraX .cxc that overlays native, MODELLER, AF3 and template and saves images.
    Paths are relative to the script's folder, which ChimeraX uses as the working
    directory while running it: `chimerax --offscreen --nogui <script>` or open it in the GUI."""
    a1, a2 = target.result_dir / "agent1", target.result_dir / "agent2"
    models = [("native", a2 / "native_eu.pdb"), ("MODELLER", a2 / "modeller_eu.pdb"),
              ("AlphaFold3", a2 / "alphafold3_eu.pdb"), ("template", a1 / "template.pdb")]
    models = [(n, p) for n, p in models if p.exists()]
    lines = ["close session", "set bgColor white", "graphics silhouettes true", "lighting soft"]
    for k, (name, path) in enumerate(models, 1):
        lines.append(f"open {os.path.relpath(path, out.parent)}")
        lines.append(f"rename #{k} {target.id}_{name}")
        lines.append(f"color #{k} {COLORS[name]}")
    lines += ["hide atoms", "show cartoons"]
    if len(models) > 1:
        lines.append(f"matchmaker #2-{len(models)} to #1")
    lines.append("view")
    lines.append(f"save {target.id}_overlay_all.png width 1600 supersample 3")
    for k, (name, _) in enumerate(models[1:], 2):
        if name == "template":
            continue
        shown = f"#1,{k}"
        lines += [f"hide #2-{len(models)} models", f"show #{k} models",
                  f"view {shown}",
                  f"save {target.id}_overlay_{name}.png width 1600 supersample 3"]
    lines.append(f"show #1-{len(models)} models")
    out.write_text("\n".join(lines) + "\n")
    return out


def make_target_figures(target: Target) -> list[Path]:
    a2 = target.result_dir / "agent2"
    metrics = json.loads((a2 / "metrics.json").read_text())
    outs = []
    if metrics["methods"]:
        p = a2 / f"{target.id}_per_residue.png"
        per_residue_plot(target, metrics, p)
        outs.append(p)
    outs.append(chimerax_script(target, a2 / f"{target.id}_overlay.cxc"))
    from . import render3d
    if render3d.available():
        outs += render3d.render_target(target)
    return outs
