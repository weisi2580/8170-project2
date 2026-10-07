"""Build the editable project slides (results/slides.pptx) from the pipeline outputs.

Tables and charts are native PowerPoint objects (edit text and numbers in PowerPoint);
structure and per-residue figures are images from results/<target>/agent2/.
Run after `tbm run-all` and `tbm report`:  python scripts/make_slides.py
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_LABEL_POSITION
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
OUT = RES / "slides.pptx"

INK, MUTED, RULE, PANEL = "0B0B0B", "52514E", "E4E3DF", "F5F4F1"
BLUE, ORANGE, GREEN, GREY = "2A78D6", "EB6834", "1BAF7A", "9A9A96"
FONT = "Calibri"
W, H = 13.333, 7.5
TARGETS = ["T1124", "T1127", "T1151s2"]
TEAM = "Parthaw Goswami · Vinaya Santhosh Kumar · Weisi Liu · Arwa Mashaqbeh"


def rgb(h: str) -> RGBColor:
    return RGBColor.from_string(h)


# ---------- data ----------

def load_rows(path: Path) -> dict:
    with open(path) as fh:
        return {(r["target"], r["method"]): r for r in csv.DictReader(fh)}


ROWS = load_rows(RES / "summary.csv")
BASE = load_rows(RES / "baseline" / "summary.csv")
DEC = {t: json.loads((RES / t / "agent1" / "decision.json").read_text()) for t in TARGETS}
MET = {t: json.loads((RES / t / "agent2" / "metrics.json").read_text()) for t in TARGETS}
CLASS = {"T1124": "TBM-easy", "T1127": "TBM-hard", "T1151s2": "FM/TBM"}
INFO = {"T1124": ("384", "7UX8", "7–384"), "T1127": ("211", "8XBP", "6–210"),
        "T1151s2": ("116", "8D5V (chain A)", "28–111")}


def val(t, method, key, nd=3):
    r = ROWS.get((t, method))
    return f"{float(r[key]):.{nd}f}" if r and r.get(key) not in (None, "") else "–"


# ---------- primitives ----------

def text(slide, x, y, w, h, paras, size=16, color=INK, bold=False, align=PP_ALIGN.LEFT,
         anchor=MSO_ANCHOR.TOP, bullet=False, spacing=6):
    """paras: str or list of str / (str, dict(size,color,bold)) tuples."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Inches(0.05)
    tf.margin_top = tf.margin_bottom = Inches(0.03)
    if isinstance(paras, str):
        paras = [paras]
    for i, p in enumerate(paras):
        s, opts = (p, {}) if isinstance(p, str) else p
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        para.alignment = align
        para.space_after = Pt(spacing)
        run = para.add_run()
        run.text = ("•  " if bullet and not opts.get("nobullet") else "") + s
        f = run.font
        f.name = FONT
        f.size = Pt(opts.get("size", size))
        f.bold = opts.get("bold", bold)
        f.color.rgb = rgb(opts.get("color", color))
    return tb


def rect(slide, x, y, w, h, fill=PANEL, line=None, shape=MSO_SHAPE.RECTANGLE):
    s = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    s.fill.solid()
    s.fill.fore_color.rgb = rgb(fill)
    if line:
        s.line.color.rgb = rgb(line)
        s.line.width = Pt(1)
    else:
        s.line.fill.background()
    s.shadow.inherit = False
    return s


def box(slide, x, y, w, h, title, body, accent=BLUE, fill="FFFFFF"):
    """Rounded card with a colored title and short body text."""
    s = rect(slide, x, y, w, h, fill=fill, line=RULE, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    s.adjustments[0] = 0.08
    tf = s.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_left = tf.margin_right = Inches(0.12)
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = title
    r.font.name, r.font.size, r.font.bold, r.font.color.rgb = FONT, Pt(15), True, rgb(accent)
    if body:
        p2 = tf.add_paragraph()
        p2.alignment = PP_ALIGN.CENTER
        r2 = p2.add_run()
        r2.text = body
        r2.font.name, r2.font.size, r2.font.color.rgb = FONT, Pt(11.5), rgb(MUTED)
    return s


def arrow(slide, x1, y1, x2, y2, color=MUTED):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1),
                                   Inches(x2), Inches(y2))
    c.line.color.rgb = rgb(color)
    c.line.width = Pt(1.75)
    ln = c.line._get_or_add_ln()
    ln.append(ln.makeelement(qn("a:tailEnd"), {"type": "triangle", "w": "med", "len": "med"}))
    return c


def picture(slide, path: Path, x, y, max_w, max_h, align="center"):
    """Place an image inside a box, keeping its aspect ratio."""
    iw, ih = Image.open(path).size
    scale = min(max_w / iw, max_h / ih)
    w, h = iw * scale, ih * scale
    dx = (max_w - w) / 2 if align == "center" else 0
    return slide.shapes.add_picture(str(path), Inches(x + dx), Inches(y + (max_h - h) / 2),
                                    Inches(w), Inches(h))


def table(slide, x, y, w, rows, col_w=None, size=12, row_h=0.36, header_fill=INK,
          highlight=None):
    """rows[0] is the header. highlight: {(r, c): hex color} for cell text."""
    n_r, n_c = len(rows), len(rows[0])
    shp = slide.shapes.add_table(n_r, n_c, Inches(x), Inches(y), Inches(w),
                                 Inches(row_h * n_r))
    tbl = shp.table
    tbl.first_row = True
    if col_w:
        for i, cw in enumerate(col_w):
            tbl.columns[i].width = Inches(cw)
    for r in range(n_r):
        tbl.rows[r].height = Inches(row_h)
        for c in range(n_c):
            cell = tbl.cell(r, c)
            cell.margin_left = cell.margin_right = Inches(0.08)
            cell.margin_top = cell.margin_bottom = Inches(0.03)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.fill.solid()
            cell.fill.fore_color.rgb = rgb(header_fill if r == 0 else
                                           ("FFFFFF" if r % 2 else PANEL))
            tf = cell.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.LEFT if c == 0 else PP_ALIGN.CENTER
            run = p.add_run()
            run.text = str(rows[r][c])
            run.font.name = FONT
            run.font.size = Pt(size)
            run.font.bold = r == 0
            color = "FFFFFF" if r == 0 else (highlight or {}).get((r, c), INK)
            run.font.color.rgb = rgb(color)
    return tbl


def new_slide(prs, title, kicker=None, notes=None):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    if kicker:
        text(s, 0.6, 0.32, 12, 0.3, kicker.upper(), size=11, color=BLUE, bold=True)
    text(s, 0.6, 0.55 if kicker else 0.45, 12.1, 0.7, title, size=28, bold=True)
    line = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(0.6), Inches(1.28),
                                  Inches(W - 0.6), Inches(1.28))
    line.line.color.rgb = rgb(RULE)
    line.line.width = Pt(1)
    n = len(prs.slides)
    text(s, W - 1.1, H - 0.42, 0.6, 0.3, str(n), size=10, color=MUTED, align=PP_ALIGN.RIGHT)
    text(s, 0.6, H - 0.42, 8, 0.3, "CMP_SC 8170 · Project 2 · Template-based modeling vs AlphaFold3",
         size=10, color=MUTED)
    if notes:
        s.notes_slide.notes_text_frame.text = notes
    return s


def legend(slide, x, y, items, size=12):
    for i, (label, color) in enumerate(items):
        rect(slide, x, y + 0.07 + i * 0, 0.22, 0.16, fill=color)
        tw = 0.12 + len(label) * size * 0.55 / 72
        text(slide, x + 0.28, y - 0.02, tw, 0.3, label, size=size, color=MUTED)
        x += 0.28 + tw + 0.2


# ---------- slides ----------

def title_slide(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    rect(s, 0, 0, 0.28, H, fill=BLUE)
    text(s, 0.9, 1.7, 11.5, 0.4, "CMP_SC 8170 · PROJECT 2", size=14, color=BLUE, bold=True)
    text(s, 0.9, 2.15, 11.5, 1.8,
         "Template-Based Modeling vs AlphaFold3 on CASP15 Targets", size=40, bold=True)
    text(s, 0.9, 3.85, 11.5, 0.9,
         "An AI-assisted MODELLER pipeline coordinated by Claude, evaluated against "
         "experimental structures", size=20, color=MUTED)
    text(s, 0.9, 5.4, 11.5, 0.4, TEAM, size=16)
    text(s, 0.9, 5.85, 11.5, 0.4, "Targets: T1124 (TBM-easy) · T1127 (TBM-hard) · "
         "T1151s2 (FM/TBM)", size=14, color=MUTED)
    s.notes_slide.notes_text_frame.text = (
        "We compare classical template-based modeling with MODELLER against AlphaFold3 on "
        "three CASP15 targets of increasing difficulty. Claude coordinates the MODELLER side "
        "and the evaluation.")


def question_slide(prs):
    s = new_slide(prs, "Where does template-based modeling fail?",
                  "Research question",
                  notes="CASP classes: TBM-easy has a clear template, TBM-hard a weak one, "
                        "FM/TBM is borderline free modeling. Scores are computed over the "
                        "CASP evaluation unit (EU) only. T1151s2 replaced T1123, for which "
                        "the profile search finds no template.")
    text(s, 0.6, 1.55, 5.6, 4.5, [
        ("Compare MODELLER (template-based) with AlphaFold3 (deep learning) on three CASP15 "
         "targets of increasing difficulty.", {}),
        ("Score both against the experimental structure over the CASP evaluation unit: "
         "TM-score, GDT-TS, lDDT, Cα RMSD.", {}),
        ("Relate MODELLER's accuracy to template identity, coverage and alignment quality.", {}),
        ("Test whether a Claude agent choosing templates changes the outcome versus a "
         "fixed-rule baseline.", {}),
    ], size=16, bullet=True, spacing=12)
    rows = [["Target", "CASP class", "Length", "PDB", "Evaluation unit"]]
    for t in TARGETS:
        n, pdb, eu = INFO[t]
        rows.append([t, CLASS[t], n, pdb, eu])
    table(s, 6.6, 1.75, 6.1, rows, col_w=[1.0, 1.25, 0.9, 1.65, 1.3], size=13, row_h=0.48)
    text(s, 6.6, 3.95, 6.1, 1.2,
         "T1151s2 replaces the original FM/TBM target T1123, for which the profile search "
         "finds no template in the pre-2022 PDB (best E = 0.5).",
         size=12, color=MUTED)


def method_slide(prs):
    s = new_slide(prs, "Pipeline: Claude coordinates, tools compute", "Method",
                  notes="Agent 1 and Agent 2 are Claude tool-use loops. Claude decides search "
                        "settings, which templates to build and which model to keep; the tools "
                        "run HMMER, MODELLER and the metrics and enforce the rules. AlphaFold3 "
                        "is run by hand on the AlphaFold Server with default settings. The "
                        "baseline runs the same tools with fixed rules: top-ranked template, "
                        "lowest-DOPE model.")
    y1, y2, bh = 1.6, 3.35, 1.15
    box(s, 0.6, 2.45, 1.9, bh, "Target FASTA", "CASP15 sequence", accent=INK)
    box(s, 3.2, y1, 3.1, bh, "Agent 1 · Claude",
        "profile search → templates → MODELLER → pick model", accent=BLUE)
    box(s, 3.2, y2, 3.1, bh, "AlphaFold3 Server", "default settings, top-ranked model",
        accent=ORANGE)
    box(s, 7.0, 2.45, 2.7, bh, "Agent 2 · Claude",
        "TM, GDT-TS, lDDT, RMSD vs experimental structure", accent=BLUE)
    box(s, 10.4, 2.45, 2.3, bh, "Report", "tables, figures, interpretation", accent=INK)
    arrow(s, 2.5, 2.8, 3.2, y1 + bh / 2)
    arrow(s, 2.5, 3.25, 3.2, y2 + bh / 2)
    arrow(s, 6.3, y1 + bh / 2, 7.0, 2.8)
    arrow(s, 6.3, y2 + bh / 2, 7.0, 3.25)
    arrow(s, 9.7, 3.02, 10.4, 3.02)
    cols = [("Claude decides", BLUE, "search settings · which templates to build (≤ 4) · "
                                     "which model to keep · error analysis"),
            ("Code enforces", INK, "no templates released after 2022-05-01 or from the target "
                                   "entry · Agent 1 never sees the answer · metrics by code"),
            ("Baseline (no AI)", GREY, "same tools, fixed rules: top-ranked template, "
                                       "lowest-DOPE model")]
    x = 0.6
    for head, color, body in cols:
        rect(s, x, 4.95, 3.9, 0.07, fill=color)
        text(s, x, 5.1, 3.9, 0.4, head, size=16, bold=True, color=color)
        text(s, x, 5.5, 3.9, 1.3, body, size=13, color=MUTED)
        x += 4.1


def search_slide(prs):
    s = new_slide(prs, "Template search: iterative profile HMM", "Method · Agent 1",
                  notes="jackhmmer round 1 compares the sequence itself; each further round "
                        "builds a profile HMM from the confident hits (E ≤ 1e-3) and searches "
                        "again. The profile knows which positions are conserved in the family, "
                        "so it finds remote homologues such as the WhiB family for T1151s2. The "
                        "same profile aligns target and template for MODELLER. GA341 near 1 "
                        "means a reliable fold; lower z-DOPE is better.")
    steps = [("Target sequence", "expression tags masked"),
             ("Round 1", "sequence vs pre-2022 PDB chains"),
             ("Rounds 2–3", "profile HMM from hits (E ≤ 1e-3)"),
             ("MODELLER", "profile alignment → 5 models")]
    y = 1.6
    for i, (head, body) in enumerate(steps):
        box(s, 0.6, y, 3.6, 0.78, head, body, accent=BLUE if i else INK)
        if i < len(steps) - 1:
            arrow(s, 2.4, y + 0.78, 2.4, y + 0.98)
        y += 0.98
    rows = [["Target", "Hits", "Templates built", "Kept", "Identity", "Coverage", "GA341"]]
    for t in TARGETS:
        d = DEC[t]
        builds = ", ".join(b["template"].split(":")[0] for b in d.get("builds", {}).values())
        al, best = d["modeller"]["alignment"], d["modeller"]["best"]
        rows.append([t, str(d["searches"][0]["n_hits"]), builds,
                     f"{d['template']['entry_id']}:{d['template']['chain']}",
                     f"{al['identity'] * 100:.0f}%", f"{al['coverage'] * 100:.0f}%",
                     f"{best['ga341']:.2f}"])
    table(s, 4.6, 1.6, 8.1, rows, col_w=[1.15, 0.75, 2.2, 1.15, 0.95, 1.05, 0.85], size=13,
          row_h=0.5)
    text(s, 4.6, 3.85, 8.1, 2.9, [
        "T1124, T1127: hundreds of family members (methyltransferases, acetyltransferases).",
        "T1151s2 (FM/TBM): only 8 hits, all WhiB-family regulators, at ~38% identity over "
        "55 residues — a remote template the profile still finds.",
        "Claude built 3 templates per target and named the risky region before evaluation: "
        "T1124 domain orientation, T1127 insertion 60–104, T1151s2 tail 85–111.",
    ], size=14, bullet=True, spacing=8)


def results_slide(prs):
    s = new_slide(prs, "AlphaFold3 is more accurate on every target", "Results",
                  notes="Scores over the CASP evaluation unit. Our TM-score matches the TMscore "
                        "program on all six models. MODELLER does best on the TBM-hard target, "
                        "so CASP difficulty labels did not predict its accuracy. The chart is a "
                        "native PowerPoint chart: right-click → Edit Data.")
    rows = [["Target", "Method", "TM ↑", "GDT-TS ↑", "lDDT ↑", "RMSD (Å) ↓"]]
    hl = {}
    for t in TARGETS:
        for m in ("MODELLER", "AlphaFold3"):
            rows.append([f"{t} ({CLASS[t]})" if m == "MODELLER" else "", m,
                         val(t, m, "tm_score"), val(t, m, "gdt_ts", 1), val(t, m, "lddt"),
                         val(t, m, "rmsd", 1)])
            hl[(len(rows) - 1, 1)] = BLUE if m == "MODELLER" else ORANGE
    table(s, 0.6, 1.6, 7.0, rows, col_w=[2.0, 1.3, 0.8, 1.0, 0.85, 1.05], size=13,
          row_h=0.5, highlight=hl)
    text(s, 0.6, 5.3, 7.0, 1.4, [
        "MODELLER is best on the TBM-hard target (0.72), not the TBM-easy one (0.54).",
        "AlphaFold3: TM 0.92–0.97 everywhere; its RMSD is raised only by floppy termini.",
    ], size=14, bullet=True, spacing=6)
    cd = CategoryChartData()
    cd.categories = TARGETS
    for m in ("MODELLER", "AlphaFold3"):
        cd.add_series(m, [round(float(ROWS[(t, m)]["tm_score"]), 3) for t in TARGETS])
    ch = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(8.0), Inches(1.5),
                            Inches(4.8), Inches(5.3), cd).chart
    ch.has_title = True
    ch.chart_title.text_frame.text = "TM-score"
    r = ch.chart_title.text_frame.paragraphs[0].runs[0]
    r.font.size, r.font.bold, r.font.name = Pt(16), True, FONT
    ch.has_legend = True
    ch.legend.position = XL_LEGEND_POSITION.BOTTOM
    ch.legend.include_in_layout = False
    ch.legend.font.size, ch.legend.font.name = Pt(12), FONT
    va = ch.value_axis
    va.maximum_scale, va.minimum_scale = 1.0, 0
    va.major_gridlines.format.line.color.rgb = rgb(RULE)
    va.tick_labels.font.size = Pt(11)
    va.format.line.fill.background()
    ch.category_axis.tick_labels.font.size = Pt(12)
    plot = ch.plots[0]
    plot.gap_width, plot.overlap = 60, -5
    plot.has_data_labels = True
    dl = plot.data_labels
    dl.font.size, dl.font.name = Pt(11), FONT
    dl.number_format, dl.number_format_is_linked = "0.00", False
    dl.position = XL_LABEL_POSITION.OUTSIDE_END
    for ser, color in zip(plot.series, (BLUE, ORANGE)):
        ser.format.fill.solid()
        ser.format.fill.fore_color.rgb = rgb(color)


STRUCT_NOTE = {
    "T1124": "N-terminal domain (7–135) misplaced by 38 Å",
    "T1127": "core 1.9 Å; insertion 60–104 has no template",
    "T1151s2": "WhiB core 1.7 Å; tail 85–111 has no template",
}


def structures_slide(prs):
    s = new_slide(prs, "Where MODELLER goes wrong", "Results",
                  notes="Grey is the experimental structure; each model is superposed with the "
                        "TM-score superposition. T1124: the catalytic domain fits, the N-terminal "
                        "domain is in a different place (Claude flagged this risk). T1127: the "
                        "template-covered GNAT core fits; the insertion with no template does not. "
                        "T1151s2: the WhiB core fits; the C-terminal tail beyond the template is "
                        "placed ~35 Å away. AlphaFold3 matches the native in all three.")
    cw, x0 = 4.0, 0.6
    for j, t in enumerate(TARGETS):
        x = x0 + j * (cw + 0.1)
        text(s, x, 1.4, cw, 0.4, f"{t} ({CLASS[t]})", size=15, bold=True, align=PP_ALIGN.CENTER)
        for i, (m, color) in enumerate((("MODELLER", BLUE), ("AlphaFold3", ORANGE))):
            y = 1.85 + i * 2.35
            img = RES / t / "agent2" / f"{t}_3d_{m}.png"
            if img.exists():
                picture(s, img, x + 0.1, y, cw - 0.2, 1.95)
            text(s, x, y + 1.95, cw, 0.3, f"{m} · TM {val(t, m, 'tm_score')}", size=12,
                 bold=True, color=color, align=PP_ALIGN.CENTER)
        text(s, x, 6.55, cw, 0.35, STRUCT_NOTE[t], size=12, color=MUTED, align=PP_ALIGN.CENTER)
    legend(s, W - 5.1, 0.62, [("experimental", GREY), ("MODELLER", BLUE),
                              ("AlphaFold3", ORANGE)], size=11)


def baseline_slide(prs):
    s = new_slide(prs, "Did the Claude agent change the outcome?", "Agent vs baseline",
                  notes="Same tools, same leakage rules; only the decisions differ. Claude built "
                        "alternatives on every target but ended up with the fixed rule's "
                        "template each time. Its value was the explicit, checkable reasoning "
                        "and correct risk predictions.")
    rows = [["Target", "Baseline (fixed rules)", "Claude agent", "TM (agent / baseline)"]]
    for t in TARGETS:
        b = BASE.get((t, "MODELLER"))
        d = DEC[t]
        tpl = f"{d['template']['entry_id']}:{d['template']['chain']}"
        n_s, n_b = len(d["searches"]), len(d.get("builds", {}))
        agent = (f"{n_s} search{'es' if n_s > 1 else ''}, {n_b} builds → kept {tpl}")
        base = f"top-ranked {b['template']}" if b else "no model"
        btm = f"{float(b['tm_score']):.3f}" if b else "–"
        rows.append([t, base, agent, f"{val(t, 'MODELLER', 'tm_score')} / {btm}"])
    table(s, 0.6, 1.6, 12.1, rows, col_w=[1.4, 3.4, 4.2, 3.1], size=14, row_h=0.55)
    text(s, 0.6, 4.1, 12.1, 2.6, [
        "Same final template on all three targets → identical scores. Claude's 6 "
        "alternative builds confirmed the top-ranked choice rather than beating it.",
        "With a good search and ranking, the fixed rule is already strong; the agent did not "
        "improve accuracy here.",
        "Where the agent helped: a written, checkable rationale for every choice, and risk "
        "predictions (domain orientation, insertion, uncovered tail) that Agent 2 confirmed.",
    ], size=15, bullet=True, spacing=10)


def gap_decomposition() -> dict:
    """TM-score of each model counted over template-covered residues only (own superposition,
    normalised by the full EU) -> how much of the AF3-MODELLER gap is in covered vs
    uncovered residues."""
    import sys
    sys.path.insert(0, str(ROOT / "src"))
    from tbm import metrics
    from tbm.modeller_build import covered_residues
    from tbm.structure import ca_coords, load_structure

    def res(p):
        ch = next(load_structure(p)[0].get_chains())
        return {r.id[1]: r for r in ch if "CA" in r}

    out = {}
    for t in TARGETS:
        a2 = RES / t / "agent2"
        nat = res(a2 / "native_eu.pdb")
        cov = set(covered_residues(RES / t / "agent1" / "alignment.ali", t))
        tm = {}
        for m, f in (("MODELLER", "modeller_eu.pdb"), ("AlphaFold3", "alphafold3_eu.pdb")):
            mod = res(a2 / f)
            c = [i for i in sorted(set(mod) & set(nat)) if i in cov]
            tm[m] = metrics.tm_score(ca_coords(mod, c), ca_coords(nat, c), len(nat))[0]
        total = (float(ROWS[(t, "AlphaFold3")]["tm_score"])
                 - float(ROWS[(t, "MODELLER")]["tm_score"]))
        covered = tm["AlphaFold3"] - tm["MODELLER"]
        out[t] = {"total": total, "covered": covered, "uncovered": total - covered,
                  "frac_covered": len([i for i in nat if i in cov]) / len(nat)}
    return out


def why_af3_slide(prs):
    s = new_slide(prs, "Why is AlphaFold3 so much better?", "Discussion",
                  notes="The TM-score gap is split by template coverage: each model's TM-score is "
                        "recomputed over template-covered residues only (normalised by the full "
                        "EU); the rest of the gap is in uncovered residues. The two parts use "
                        "separate superpositions, so the split is approximate. Homologues at "
                        "30–40% identity typically differ by 1.5–2.5 Å, which caps how close a "
                        "copied template can be.")
    gap = gap_decomposition()
    rows = [["Target", "EU covered", "TM gap", "in covered residues",
             "in uncovered residues"]]
    hl = {}
    for i, t in enumerate(TARGETS, 1):
        g = gap[t]
        rows.append([t, f"{g['frac_covered'] * 100:.0f}%", f"+{g['total']:.2f}",
                     f"+{g['covered']:.2f}", f"+{g['uncovered']:.2f}"])
        hl[(i, 3 if g["covered"] > g["uncovered"] else 4)] = ORANGE
    table(s, 0.6, 1.6, 6.6, rows, col_w=[1.2, 1.2, 1.1, 1.55, 1.55], size=13, row_h=0.5,
          highlight=hl)
    text(s, 0.6, 3.75, 6.6, 3.2, [
        ("Where MODELLER loses (larger share in orange):", {"bold": True, "size": 14}),
        ("No template, no structure: the T1127 insertion and the T1151s2 tail exist in no "
         "template, so MODELLER guesses them (22–35 Å off).", {"size": 13}),
        ("Covered but misplaced: T1124's N-terminal domain is template-covered (27% "
         "identity) yet lands 38 Å from the native; the domain arrangement is wrong.",
         {"size": 13}),
        ("Copying a relative caps accuracy: covered core 3.2 Å (T1127) and 2.2 Å (T1151s2) "
         "Cα RMSD vs 0.8 / 0.7 Å for AlphaFold3 on the same residues.", {"size": 13}),
    ], spacing=6)
    rect(s, 7.6, 1.6, 5.1, 5.1, fill=PANEL)
    rect(s, 7.6, 1.6, 0.09, 5.1, fill=ORANGE)
    text(s, 7.9, 1.8, 4.6, 4.8, [
        ("Why AlphaFold3 avoids this", {"bold": True, "size": 17}),
        ("Learned from the whole PDB: it predicts this sequence's own structure instead of "
         "copying one relative's coordinates.", {"size": 14}),
        ("Co-evolution from deep sequence alignments: positions that mutate together are "
         "in contact, which constrains regions no template covers.", {"size": 14}),
        ("Templates are hints, not scaffolds: several are combined and adjusted to the "
         "target, so domain arrangement is not inherited from one homologue.",
         {"size": 14}),
        ("Result: accurate even where MODELLER had nothing (T1127 insertion 0.9 Å, "
         "T1151s2 tail 1.5 Å).", {"size": 14, "color": MUTED}),
    ], bullet=False, spacing=10)


def conclusion_slide(prs):
    s = new_slide(prs, "Conclusions", "Summary",
                  notes="Limitations: three targets, one model per method; single-template "
                        "models; Claude's rejected builds were not scored; scores cover the CASP "
                        "evaluation units only, and T1151s2 is one chain of a complex. "
                        "Reproduce: conda env create -f environment.yml; tbm run-all; "
                        "tbm --baseline run-all; python scripts/make_slides.py")
    text(s, 0.6, 1.6, 7.4, 5, [
        "MODELLER is only as good as its template: accurate where the template covers (core "
        "~2 Å), wrong where it does not.",
        "A profile search makes template-based modeling possible even for the FM/TBM target "
        "(T1151s2, TM 0.52).",
        "AlphaFold3 outperforms MODELLER on all three targets (TM +0.25 to +0.40), mostly in "
        "regions templates do not cover or place correctly.",
        "The Claude agent matched the fixed rule's choices and predicted each failure "
        "region: it added transparency, not accuracy.",
    ], size=17, bullet=True, spacing=12)
    rect(s, 8.5, 1.6, 4.2, 4.6, fill=PANEL)
    text(s, 8.75, 1.8, 3.8, 4.3, [
        ("Limitations", {"bold": True, "size": 16}),
        ("Three targets, one model per method: case studies, not trends.", {"size": 13}),
        ("Single-template models only.", {"size": 13}),
        ("Claude's rejected builds were not scored against the native.", {"size": 13}),
        ("CASP evaluation units only; T1151s2 scored as a monomer.", {"size": 13}),
        ("AlphaFold Server also uses PDB templates: method vs method, not template vs "
         "none.", {"size": 13}),
    ], spacing=8)


def main():
    prs = Presentation()
    prs.slide_width, prs.slide_height = Emu(int(Inches(W))), Emu(int(Inches(H)))
    for build in (title_slide, question_slide, method_slide, search_slide, results_slide,
                  structures_slide, why_af3_slide, baseline_slide, conclusion_slide):
        build(prs)
    prs.save(OUT)
    print(f"{len(prs.slides)} slides -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
