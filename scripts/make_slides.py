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
                        "CASP evaluation unit (EU) only. T1151s2 replaced T1123, which had no "
                        "sequence-detectable template in the PDB.")
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
         "T1151s2 replaces the original FM/TBM target T1123, for which neither RCSB nor a "
         "whole-PDB MMseqs2 search found any homologue other than its own structure.",
         size=12, color=MUTED)


def pipeline_slide(prs):
    s = new_slide(prs, "Pipeline: Claude coordinates, tools compute", "Method",
                  notes="Agent 1 and Agent 2 are Claude tool-use loops. Claude picks search "
                        "settings, which templates to build and which model to keep; the tools "
                        "run RCSB / MMseqs2 search, MODELLER and the metrics. AlphaFold3 is run "
                        "by hand on the AlphaFold Server with default settings.")
    y1, y2, bh = 1.75, 3.85, 1.25
    box(s, 0.6, 2.8, 1.9, bh, "Target FASTA", "CASP15 sequence", accent=INK)
    box(s, 3.2, y1, 3.0, bh, "Agent 1 · Claude",
        "template search → leakage filter → align2d / automodel → pick model", accent=BLUE)
    box(s, 3.2, y2, 3.0, bh, "AlphaFold3 Server", "default settings, top-ranked model",
        accent=ORANGE)
    box(s, 6.9, 2.8, 2.6, bh, "Agent 2 · Claude",
        "TM, GDT-TS, lDDT, RMSD vs experimental structure", accent=BLUE)
    box(s, 10.2, 2.8, 2.5, bh, "Report", "tables, figures, Claude's draft interpretation",
        accent=INK)
    box(s, 6.9, 5.0, 2.6, 0.95, "Experimental structure", "RCSB PDB, Agent 2 only",
        accent=GREY)
    arrow(s, 2.5, 3.2, 3.2, y1 + bh / 2)
    arrow(s, 2.5, 3.65, 3.2, y2 + bh / 2)
    arrow(s, 6.2, y1 + bh / 2, 6.9, 3.2)
    arrow(s, 6.2, y2 + bh / 2, 6.9, 3.65)
    arrow(s, 8.2, 5.0, 8.2, 2.8 + bh)
    arrow(s, 9.5, 3.42, 10.2, 3.42)
    text(s, 0.6, 6.25, 12.1, 0.6,
         "Every Claude step (reasoning summary, tool calls, results) is saved as "
         "agent_transcript.md; a score-only baseline runs the same tools without Claude.",
         size=13, color=MUTED)


def agent_slide(prs):
    s = new_slide(prs, "What Claude decides, and what the code enforces", "Method",
                  notes="The hard rules are in code, so the agent cannot leak the answer: "
                        "Agent 1 never sees the experimental structure and its task prompt "
                        "contains no PDB ID. The baseline uses the same search and MODELLER "
                        "but picks the top-ranked template and the lowest-DOPE model.")
    cols = [
        ("Claude decides", BLUE, [
            "search backend and E-value cutoff (RCSB or local MMseqs2)",
            "which candidate templates to build (up to 4)",
            "which build and model to keep, or no template at all",
            "Agent 2: which errors to inspect and how to explain them",
            "the draft interpretation of the whole comparison"]),
        ("Code enforces", INK, [
            "leakage control: target's own PDB entry and templates released after "
            "2022-05-01 are excluded",
            "Agent 1 never reads the experimental structure",
            "metrics are computed by code and cross-checked with TMscore",
            "Claude may only use the numbers the tools return"]),
        ("Baseline (no AI)", GREY, [
            "same search and MODELLER",
            "top-ranked template by a fixed score (identity, coverage, E-value, "
            "resolution, completeness)",
            "lowest-DOPE model",
            "stops if the default RCSB search finds no eligible template"]),
    ]
    x = 0.6
    for title, color, items in cols:
        rect(s, x, 1.6, 3.9, 0.08, fill=color)
        text(s, x, 1.8, 3.9, 0.5, title, size=18, bold=True, color=color)
        text(s, x, 2.35, 3.9, 4.2, items, size=14, bullet=True, spacing=10)
        x += 4.1


def template_slide(prs):
    s = new_slide(prs, "Agent 1: template decisions", "Results",
                  notes="Identity and coverage are from MODELLER's align2d alignment over the "
                        "full sequence. GA341 near 1 means a reliable fold; z-DOPE below 0 is "
                        "native-like. For T1151s2 the default search found only the target's "
                        "own structure; Claude widened the search to E ≤ 1000 and used a weak "
                        "WhiB4 hit, flagging the model as low confidence.")
    rows = [["Target", "Searches", "Templates built", "Kept", "align2d identity",
             "align2d coverage", "GA341", "z-DOPE"]]
    for t in TARGETS:
        d = DEC[t]
        searches = " + ".join(f"{q['backend']} (E≤{q['evalue_cutoff']:g})" for q in d["searches"])
        builds = ", ".join(b["template"] for b in d.get("builds", {}).values())
        al, best = d["modeller"]["alignment"], d["modeller"]["best"]
        rows.append([f"{t}\n{CLASS[t]}", searches, builds,
                     f"{d['template']['entry_id']}:{d['template']['chain']}",
                     f"{al['identity'] * 100:.1f}%", f"{al['coverage'] * 100:.1f}%",
                     f"{best['ga341']:.2f}", f"{best['zdope']:+.2f}"])
    hl = {(3, 6): ORANGE, (3, 7): ORANGE}
    table(s, 0.6, 1.6, 12.1, rows, col_w=[1.3, 2.3, 2.3, 1.15, 1.35, 1.35, 1.1, 1.25],
          size=13, row_h=0.62, highlight=hl)
    text(s, 0.6, 4.4, 12.1, 2.2, [
        "T1124 and T1127: clear homologues (E ≈ 1e-16 to 1e-18); Claude built 2–3 "
        "alternatives and kept the best z-DOPE / highest identity.",
        "T1151s2: the default search returns only 8D5V itself. Claude widened to local "
        "MMseqs2 (E ≤ 1000) and chose 7F7N:A (WhiB4, E = 3.9), citing WhiB-like cysteine "
        "spacing. MODELLER's own scores already warn: GA341 ≈ 0.01, z-DOPE +1.9.",
    ], size=14, bullet=True, spacing=10)


def results_table_slide(prs):
    s = new_slide(prs, "AlphaFold3 is more accurate on every target and metric", "Results",
                  notes="Scores over the CASP evaluation unit. TM-score and GDT-TS reward the "
                        "fraction of the structure that is right; RMSD is dominated by the worst "
                        "parts. Our TM-score matches the TMscore program on all six models.")
    rows = [["Target", "Method", "TM-score ↑", "GDT-TS ↑", "lDDT ↑", "Cα RMSD (Å) ↓"]]
    hl = {}
    for t in TARGETS:
        for m in ("MODELLER", "AlphaFold3"):
            rows.append([f"{t} ({CLASS[t]})" if m == "MODELLER" else "", m,
                         val(t, m, "tm_score"), val(t, m, "gdt_ts", 1), val(t, m, "lddt"),
                         val(t, m, "rmsd", 2)])
            hl[(len(rows) - 1, 1)] = BLUE if m == "MODELLER" else ORANGE
    table(s, 0.6, 1.6, 7.4, rows, col_w=[2.0, 1.3, 1.0, 1.0, 0.9, 1.2], size=13, row_h=0.5,
          highlight=hl)
    gap = [float(ROWS[(t, "AlphaFold3")]["tm_score"]) - float(ROWS[(t, "MODELLER")]["tm_score"])
           for t in TARGETS]
    text(s, 8.4, 1.6, 4.3, 4.8, [
        ("TM-score gap (AF3 − MODELLER)", {"bold": True, "size": 15}),
        *[(f"{t}: +{g:.2f}", {"size": 15}) for t, g in zip(TARGETS, gap)],
        ("", {}),
        ("MODELLER is best on the TBM-hard target (TM 0.66), not the TBM-easy one: "
         "CASP difficulty labels did not predict MODELLER's accuracy here.", {"size": 14}),
        ("On T1151s2 the MODELLER model is essentially random (TM < 0.17).",
         {"size": 14}),
    ], spacing=8)


def chart_slide(prs):
    s = new_slide(prs, "Scores at a glance", "Results",
                  notes="Native PowerPoint charts: right-click → Edit Data to change values.")
    specs = [("TM-score", "tm_score", 1.0), ("GDT-TS", "gdt_ts", 100.0), ("lDDT", "lddt", 1.0)]
    x = 0.5
    for title, key, ymax in specs:
        cd = CategoryChartData()
        cd.categories = TARGETS
        for m in ("MODELLER", "AlphaFold3"):
            cd.add_series(m, [round(float(ROWS[(t, m)][key]), 3) for t in TARGETS])
        gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(x), Inches(1.5),
                                Inches(4.1), Inches(5.2), cd)
        ch = gf.chart
        ch.has_title = True
        ch.chart_title.text_frame.text = title
        tp = ch.chart_title.text_frame.paragraphs[0]
        tp.runs[0].font.size, tp.runs[0].font.bold, tp.runs[0].font.name = Pt(16), True, FONT
        ch.has_legend = True
        ch.legend.position = XL_LEGEND_POSITION.BOTTOM
        ch.legend.include_in_layout = False
        ch.legend.font.size, ch.legend.font.name = Pt(12), FONT
        va = ch.value_axis
        va.maximum_scale, va.minimum_scale = ymax, 0
        va.has_major_gridlines = True
        va.major_gridlines.format.line.color.rgb = rgb(RULE)
        va.tick_labels.font.size = Pt(11)
        va.format.line.fill.background()
        ch.category_axis.tick_labels.font.size = Pt(12)
        plot = ch.plots[0]
        plot.gap_width, plot.overlap = 60, -5
        plot.has_data_labels = True
        dl = plot.data_labels
        dl.font.size, dl.font.name = Pt(10), FONT
        dl.number_format = "0.0" if key == "gdt_ts" else "0.00"
        dl.number_format_is_linked = False
        dl.position = XL_LABEL_POSITION.OUTSIDE_END
        for ser, color in zip(plot.series, (BLUE, ORANGE)):
            ser.format.fill.solid()
            ser.format.fill.fore_color.rgb = rgb(color)
        x += 4.15


TARGET_TEXT = {
    "T1124": ("T1124 (TBM-easy): right domains, wrong arrangement", [
        "Template 5I2H:A (O-methyltransferase), 29% identity, 87.6% of the EU aligned.",
        "Residues 7–135 are placed as a block in the wrong position: mean Cα error 37.7 Å, "
        "while local lDDT stays moderate → a domain-placement error, not a local-fold error.",
        "z-DOPE (−0.05) and GA341 (1.0) looked good: they cannot detect a misplaced domain.",
        "AlphaFold3 places the N-terminal region correctly; its 6.6 Å RMSD comes from the "
        "disordered C-terminal tail (369–384).",
    ], "Grey = experimental (7UX8). After superposing on the C-terminal domain, MODELLER's "
       "N-terminal block (blue) and the native one (grey) sit in different places. Hypothesis "
       "from Agent 2: the template's dimer context, not tested. AlphaFold Server used other "
       "O-methyltransferase templates (4Z2Y, 4A6D, 3GWZ, 6C5B)."),
    "T1127": ("T1127 (TBM-hard): core right, insertion missing", [
        "Template 2FE7:B (GNAT acetyltransferase), 40% identity, 77% coverage.",
        "Template-covered residues: mean Cα error 3.3 Å; the 43 uncovered residues "
        "(insertion ~51–113): 24.8 Å.",
        "Missing template coverage explains most of MODELLER's error (RMSD 13.5 Å).",
        "AlphaFold3 models the insertion correctly too (0.8 Å on uncovered residues).",
    ], "Claude predicted this failure before evaluation: Agent 1 noted that ~23% of the EU, "
       "mostly the insertion, had no template and would probably be inaccurate."),
    "T1151s2": ("T1151s2 (FM/TBM): weak template, wrong fold", [
        "Our MMseqs2 search found only a weak hit: 7F7N:A (WhiB4), E = 3.9, covering 42–79.",
        "align2d stretched it to 96% of the EU, but covered residues are off by 27.6 Å "
        "on average; only ~13 residues (84–96) are within 4 Å.",
        "Coverage is only meaningful when the homology is real.",
        "AlphaFold3 (TM 0.92) used 4 WhiB templates (5OAY, 6ONO, 7KIF, 7KUG), all "
        "pre-2022 and allowed by our cutoff, which our sequence search missed.",
    ], "MODELLER's own scores flagged the model (GA341 ≈ 0.01, z-DOPE +1.9) and Claude labelled "
       "it low confidence. The score-only baseline produced no MODELLER model for this target."),
}


def target_slides(prs):
    for t in TARGETS:
        title, bullets, note = TARGET_TEXT[t]
        s = new_slide(prs, title, f"Results · {t}", notes=note)
        a2 = RES / t / "agent2"
        for i, (m, color) in enumerate((("MODELLER", BLUE), ("AlphaFold3", ORANGE))):
            x = 0.6 + i * 3.15
            img = a2 / f"{t}_3d_{m}.png"
            if img.exists():
                picture(s, img, x, 1.85, 3.0, 2.75)
            text(s, x, 1.45, 3.0, 0.35, m, size=15, bold=True, color=color,
                 align=PP_ALIGN.CENTER)
            text(s, x - 0.05, 4.62, 3.1, 0.32,
                 f"TM {val(t, m, 'tm_score')} · GDT-TS {val(t, m, 'gdt_ts', 1)} · "
                 f"RMSD {val(t, m, 'rmsd', 1)} Å", size=10.5, color=MUTED,
                 align=PP_ALIGN.CENTER)
        legend(s, 1.0, 5.02, [("experimental", GREY), ("MODELLER", BLUE),
                             ("AlphaFold3", ORANGE)])
        text(s, 0.6, 5.45, 6.1, 1.5, [(b, {}) for b in bullets[:2]], size=13, bullet=True,
             spacing=6)
        picture(s, a2 / f"{t}_per_residue.png", 6.95, 1.45, 5.8, 3.25)
        text(s, 6.95, 4.75, 5.8, 0.35, "Per-residue error · shaded = aligned to the template",
             size=11, color=MUTED, align=PP_ALIGN.CENTER)
        text(s, 6.95, 5.2, 5.8, 1.8, [(b, {}) for b in bullets[2:]], size=13, bullet=True,
             spacing=6)


def baseline_slide(prs):
    s = new_slide(prs, "Did the Claude agent change the outcome?", "Agent vs baseline",
                  notes="Same tools, same leakage rules; only the decisions differ. On the two "
                        "targets with real templates, Claude made the same final choice as the "
                        "fixed rules. On T1151s2 it widened the search and produced a model, "
                        "which was wrong; its value there was transparency about risk.")
    rows = [["Target", "Baseline (fixed rules)", "Claude agent", "MODELLER TM (agent / baseline)"]]
    for t in TARGETS:
        b = BASE.get((t, "MODELLER"))
        d = DEC[t]
        tpl = f"{d['template']['entry_id']}:{d['template']['chain']}"
        n_b = len(d.get("builds", {}))
        agent = f"built {n_b} → kept {tpl}" if n_b > 1 else f"widened search → kept {tpl} (low conf.)"
        base = b["template"] if b else "no eligible template → no model"
        btm = f"{float(b['tm_score']):.3f}" if b else "–"
        rows.append([t, base, agent, f"{val(t, 'MODELLER', 'tm_score')} / {btm}"])
    table(s, 0.6, 1.6, 12.1, rows, col_w=[1.4, 3.6, 4.0, 3.1], size=14, row_h=0.55)
    text(s, 0.6, 4.1, 12.1, 2.6, [
        "Same final template on T1124 and T1127 → identical scores; Claude's extra builds "
        "did not beat the top-ranked template.",
        "T1151s2: Claude turned \"no model\" into a model, but with no structural value "
        "(GDT-TS 19.0).",
        "Where the agent helped: explicit risk statements (insertion in T1127, low confidence "
        "in T1151s2) that Agent 2 later confirmed, and a full reasoning trace for every choice.",
    ], size=15, bullet=True, spacing=10)


def findings_slide(prs):
    s = new_slide(prs, "Key findings", "Discussion",
                  notes="Three targets is a small sample: these are case studies, not trends.")
    items = [
        ("Template coverage sets the ceiling", BLUE,
         "T1127: covered core 3.3 Å vs uncovered insertion 24.8 Å. Residues without a "
         "template are essentially guessed."),
        ("Coverage is not enough", BLUE,
         "T1124: 88% aligned, but a whole domain is misplaced. Weak identity (~29%) can "
         "copy the wrong domain arrangement."),
        ("Weak hits can mislead", ORANGE,
         "T1151s2: an E = 3.9 hit stretched to 96% coverage gives a wrong fold. "
         "GA341 and z-DOPE flagged it; TBM needs real homology."),
        ("Template search is the bottleneck", ORANGE,
         "AlphaFold3 (TM 0.92–0.97) also used templates: for T1151s2 four WhiB structures "
         "our MMseqs2 search missed. Profile search plus learned structure wins."),
    ]
    for i, (head, color, body) in enumerate(items):
        x, y = 0.6 + (i % 2) * 6.15, 1.6 + (i // 2) * 2.55
        rect(s, x, y, 5.95, 2.3, fill=PANEL)
        rect(s, x, y, 0.09, 2.3, fill=color)
        text(s, x + 0.3, y + 0.2, 5.5, 0.5, head, size=19, bold=True)
        text(s, x + 0.3, y + 0.8, 5.5, 1.4, body, size=14, color=MUTED)


def limits_slide(prs):
    s = new_slide(prs, "Limitations", "Discussion")
    text(s, 0.6, 1.6, 12.1, 5, [
        "Three targets, one MODELLER and one AlphaFold3 model each: case studies, not trends.",
        "Our template search is sequence-based (RCSB / MMseqs2); a profile method such as "
        "HHpred would likely have found the WhiB templates for T1151s2.",
        "Only single-template models; multi-template MODELLER runs were not tried.",
        "Alternative builds Claude rejected were not scored against the experimental "
        "structure, so we cannot say whether they would have been better.",
        "Evaluation is limited to the CASP evaluation units; T1127 has 7 unobserved EU "
        "residues, and T1151s2 is one chain of a complex (scored as a monomer).",
        "AlphaFold Server runs its own profile-based template search: it found eligible "
        "templates (all released before 2022-05) that our MMseqs2 search missed, e.g. four "
        "WhiB structures for T1151s2. The comparison is not template-free vs template-based.",
    ], size=16, bullet=True, spacing=12)


def conclusion_slide(prs):
    s = new_slide(prs, "Conclusion", "Summary",
                  notes="Reproduce: conda env create -f environment.yml; tbm run-all; "
                        "tbm report; python scripts/make_slides.py")
    text(s, 0.6, 1.6, 7.6, 4.5, [
        "MODELLER is only as good as its template: accurate where coverage and homology are "
        "real, wrong elsewhere.",
        "AlphaFold3 outperforms MODELLER on all three targets (TM +0.31 to +0.75).",
        "An AI coordinator adds transparency and sensible risk flags, but cannot make up "
        "for a template search that misses remote homologues.",
    ], size=18, bullet=True, spacing=14)
    rect(s, 8.6, 1.6, 4.1, 4.4, fill=PANEL)
    text(s, 8.85, 1.8, 3.7, 4.1, [
        ("Reproduce", {"bold": True, "size": 15}),
        ("conda env create -f environment.yml", {"size": 12}),
        ("tbm run-all", {"size": 12}),
        ("tbm --baseline run-all", {"size": 12}),
        ("python scripts/make_slides.py", {"size": 12}),
        ("", {}),
        ("Outputs in results/: summary tables, figures, Claude transcripts and analyses.",
         {"size": 12, "color": MUTED}),
    ], spacing=6)


def main():
    prs = Presentation()
    prs.slide_width, prs.slide_height = Emu(int(Inches(W))), Emu(int(Inches(H)))
    title_slide(prs)
    question_slide(prs)
    pipeline_slide(prs)
    agent_slide(prs)
    template_slide(prs)
    results_table_slide(prs)
    chart_slide(prs)
    target_slides(prs)
    baseline_slide(prs)
    findings_slide(prs)
    limits_slide(prs)
    conclusion_slide(prs)
    prs.save(OUT)
    print(f"{len(prs.slides)} slides -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
