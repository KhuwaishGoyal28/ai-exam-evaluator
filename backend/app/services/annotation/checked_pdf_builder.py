"""
Builds the final checked PDF using PyMuPDF (fitz).

Pipeline:
  1. For each original page image → draw red-ink marks at y_percent positions
  2. Append a final score-sheet page (Roundtable IAS style)

Red-ink marks per annotation_type:
  PRAISE          → green tick (✓) on left + green underline + RIGHT_MARGIN box
  CORRECTION      → red cross (✗) on left + red wavy underline + RIGHT_MARGIN box
  STRUCTURAL_NOTE → violet margin box only (no inline mark)

mark_symbol overrides:
  TICK        → ✓  (green)
  CROSS       → ✗  (red)
  CIRCLE      → red ellipse around text region
  UNDERLINE   → straight coloured underline
  MARGIN_BOX  → coloured box in specified margin position only

All positions are computed from y_percent (0=top, 100=bottom of page).
"""
from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.models.domain.evaluation import (
    EvaluationResult, PageAnnotation, ParameterBreakdown,
)
from app.core.logging import get_logger

logger = get_logger(__name__)

# ── Colour palette (r, g, b) 0–1 ─────────────────────────────────────────────
_RED    = (0.86, 0.10, 0.10)
_GREEN  = (0.08, 0.63, 0.28)
_BLUE   = (0.15, 0.39, 0.92)
_VIOLET = (0.39, 0.13, 0.83)
_AMBER  = (0.85, 0.53, 0.04)
_DARK   = (0.06, 0.09, 0.16)
_LIGHT  = (0.72, 0.72, 0.78)
_WHITE  = (1.00, 1.00, 1.00)

# Margin panel on the right side of each page (proportion of page width)
_MARGIN_RATIO   = 0.28      # 28% right strip reserved for examiner notes
_MARGIN_PAD     = 6         # pt padding inside margin boxes
_BOX_MIN_HEIGHT = 22        # pt minimum comment box height


def build_checked_pdf(
    page_images: list,          # list[PIL.Image.Image]
    evaluation: EvaluationResult,
    question: str | None,
    exam_type: str,
    job_id: str,
) -> bytes:
    """
    Build the complete checked PDF.
    Returns raw PDF bytes ready for storage / download.
    """
    try:
        import fitz
    except ImportError:
        logger.warning("pymupdf_not_installed_fallback_reportlab")
        return _build_fallback_pdf(page_images, evaluation, question, exam_type, job_id)

    doc = fitz.open()

    for page_num_0, pil_img in enumerate(page_images):
        page_num_1 = page_num_0 + 1
        img_bytes  = _pil_to_jpeg_bytes(pil_img)
        annotations = evaluation.annotations_for_page(page_num_1)

        _add_annotated_page(doc, img_bytes, annotations, page_num_1,
                            len(page_images), evaluation)

    # Final score sheet page
    _add_score_sheet(doc, evaluation, question, exam_type, job_id)

    pdf_bytes = doc.tobytes(garbage=4, deflate=True)
    doc.close()
    logger.info("checked_pdf_built_pymupdf",
                pages=len(page_images) + 1,
                size_kb=len(pdf_bytes) // 1024)
    return pdf_bytes


# ── Page rendering ────────────────────────────────────────────────────────────

def _add_annotated_page(
    doc,
    img_bytes: bytes,
    annotations: list[PageAnnotation],
    page_num: int,
    total_pages: int,
    evaluation: EvaluationResult,
) -> None:
    """Insert one annotated page into the fitz document."""
    import fitz

    # Insert image as a new page
    img_rect = fitz.Rect(0, 0, 595, 842)   # A4 points
    page = doc.new_page(width=595, height=842)
    page.insert_image(img_rect, stream=img_bytes)

    W, H = 595, 842
    margin_x = W * (1 - _MARGIN_RATIO)     # x where margin panel starts

    # ── Draw margin panel background ──────────────────────────────────────
    margin_rect = fitz.Rect(margin_x, 0, W, H)
    page.draw_rect(margin_rect, color=None, fill=(0.97, 0.97, 0.99))

    # Separator line
    page.draw_line(fitz.Point(margin_x, 0), fitz.Point(margin_x, H),
                   color=_LIGHT, width=0.8)

    # Margin header
    page.insert_text(
        fitz.Point(margin_x + 5, 16),
        "Examiner's Notes",
        fontsize=7, color=_VIOLET,
        fontname="helv",
    )
    page.draw_line(
        fitz.Point(margin_x + 4, 20),
        fitz.Point(W - 4, 20),
        color=_LIGHT, width=0.4,
    )

    # ── Draw each annotation ──────────────────────────────────────────────
    next_margin_y = 26.0    # next available y in the margin panel

    # Sort annotations top-to-bottom by y_percent
    sorted_ann = sorted(annotations, key=lambda a: a.location.y_percent)

    for ann in sorted_ann:
        y_pt = (ann.location.y_percent / 100.0) * H   # convert % → points

        colour  = _annotation_colour(ann)
        symbol  = _annotation_symbol(ann)

        # ── Inline mark on the answer body ────────────────────────────────
        left_x = 8.0    # left edge for tick/cross glyphs
        text_x = 30.0   # approximate start of handwritten text

        if ann.mark_symbol in ("TICK", "CROSS") or ann.annotation_type == "PRAISE":
            # Draw glyph on left margin of answer area
            page.insert_text(
                fitz.Point(left_x, y_pt),
                symbol,
                fontsize=11, color=colour,
                fontname="helv",
            )

        if ann.mark_symbol == "UNDERLINE" or ann.annotation_type == "PRAISE":
            # Green underline across ~50% of text width
            page.draw_line(
                fitz.Point(text_x, y_pt + 3),
                fitz.Point(margin_x - 20, y_pt + 3),
                color=colour, width=1.2,
            )

        elif ann.mark_symbol == "UNDERLINE" or ann.annotation_type == "CORRECTION":
            # Wavy red underline
            _draw_wavy_underline(page, text_x, y_pt + 3,
                                  margin_x - 20, colour)

        elif ann.mark_symbol == "CIRCLE":
            # Circle around a small region at y_pt
            page.draw_oval(
                fitz.Rect(text_x, y_pt - 8, text_x + 80, y_pt + 4),
                color=colour, width=1.0,
            )

        # Small diagonal arrow pointing to margin
        arrow_tip_x = margin_x - 4
        page.draw_line(
            fitz.Point(margin_x - 18, y_pt),
            fitz.Point(arrow_tip_x, y_pt),
            color=colour, width=0.6,
        )

        # ── Margin comment box ─────────────────────────────────────────────
        box_y = max(next_margin_y, y_pt - 6)
        box_y = min(box_y, H - _BOX_MIN_HEIGHT - 4)

        box_h = _draw_margin_box(
            page, ann.annotation_text, ann.annotation_type,
            margin_x + 3, box_y, W - 4, colour,
        )
        next_margin_y = box_y + box_h + 4

    # ── Page footer ───────────────────────────────────────────────────────
    page.insert_text(
        fitz.Point(8, H - 8),
        f"Page {page_num} of {total_pages + 1}",
        fontsize=6, color=_LIGHT, fontname="helv",
    )
    page.insert_text(
        fitz.Point(W - 120, H - 8),
        "EvalPro — Checked Answer",
        fontsize=6, color=_LIGHT, fontname="helv",
    )


def _draw_margin_box(
    page, text: str, ann_type: str,
    x1: float, y1: float, x2: float,
    colour: tuple,
) -> float:
    """
    Draw a coloured comment box in the margin.
    Returns the height of the box drawn.
    """
    import fitz

    BG = {
        "PRAISE":          (0.90, 0.98, 0.93),
        "CORRECTION":      (0.99, 0.92, 0.92),
        "STRUCTURAL_NOTE": (0.93, 0.92, 0.99),
    }.get(ann_type, (0.95, 0.95, 0.99))

    # Word-wrap text at ~28 chars per line (rough estimate for 6pt font)
    words   = text.split()
    lines   : list[str] = []
    current = ""
    for w in words:
        candidate = f"{current} {w}".strip()
        if len(candidate) <= 28:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = w
    if current:
        lines.append(current)
    lines = lines or [""]

    LINE_H  = 9.0
    box_h   = max(_BOX_MIN_HEIGHT, _MARGIN_PAD * 2 + LINE_H * len(lines))
    box_rect = fitz.Rect(x1, y1, x2, y1 + box_h)

    # Background
    page.draw_rect(box_rect, color=None, fill=BG)
    # Left accent bar
    page.draw_rect(fitz.Rect(x1, y1, x1 + 3, y1 + box_h),
                   color=None, fill=colour)

    # Text lines
    for i, line in enumerate(lines):
        page.insert_text(
            fitz.Point(x1 + 6, y1 + _MARGIN_PAD + LINE_H * (i + 0.75)),
            line,
            fontsize=6, color=_DARK, fontname="helv",
        )

    return box_h


def _draw_wavy_underline(
    page, x1: float, y: float, x2: float, colour: tuple
) -> None:
    """Approximate wavy underline with short alternating diagonal segments."""
    import fitz
    amplitude = 2.5
    period    = 8.0
    x = x1
    toggle = 1
    while x < x2 - period:
        nx = min(x + period, x2)
        ny = y + amplitude * toggle
        page.draw_line(fitz.Point(x, y), fitz.Point(nx, ny),
                       color=colour, width=1.0)
        toggle = -toggle
        x = nx


# ── Score sheet page ──────────────────────────────────────────────────────────

def _add_score_sheet(
    doc,
    evaluation: EvaluationResult,
    question: str | None,
    exam_type: str,
    job_id: str,
) -> None:
    """Append the final score sheet page (Roundtable IAS style)."""
    import fitz

    page = doc.new_page(width=595, height=842)
    W, H = 595, 842
    MARGIN = 25.0
    now = datetime.now(tz=timezone.utc).strftime("%d %b %Y")

    total   = evaluation.score_summary.total_score
    max_s   = evaluation.score_summary.max_score
    grade   = evaluation.score_summary.grade
    pct     = total / max_s if max_s else 0
    g_colour = (
        _GREEN  if pct >= 0.8 else
        _VIOLET if pct >= 0.6 else
        _AMBER  if pct >= 0.4 else
        _RED
    )

    # ── Header bar ────────────────────────────────────────────────────────
    page.draw_rect(fitz.Rect(0, 0, W, 36), color=None, fill=_VIOLET)
    page.insert_text(fitz.Point(MARGIN, 11),
                     "ROUNDTABLE IAS  ·  ESSAY MENTORSHIP CELL",
                     fontsize=8, color=_WHITE, fontname="helv")
    page.insert_text(fitz.Point(MARGIN, 26),
                     "Essay Evaluation Sheet",
                     fontsize=13, color=_WHITE, fontname="helv")
    page.insert_text(fitz.Point(W - 130, 11),
                     f"Paper: Essay  ·  Word limit: 1200",
                     fontsize=6, color=_WHITE, fontname="helv")
    page.insert_text(fitz.Point(W - 90, 21),
                     f"Evaluated: {now}",
                     fontsize=6, color=_WHITE, fontname="helv")

    y = 50.0

    # ── Topic block ───────────────────────────────────────────────────────
    topic = (question or exam_type or "Essay")[:110]
    page.draw_rect(fitz.Rect(MARGIN, y, W - MARGIN, y + 22),
                   color=_VIOLET, fill=(0.94, 0.94, 0.98), width=0.4)
    page.insert_text(fitz.Point(MARGIN + 4, y + 7),
                     "TOPIC", fontsize=6, color=_VIOLET, fontname="helv")
    page.insert_text(fitz.Point(MARGIN + 4, y + 17),
                     f'"{topic}"',
                     fontsize=7.5, color=_DARK, fontname="helv")
    y += 28.0

    # ── Score hero ────────────────────────────────────────────────────────
    page.draw_rect(fitz.Rect(MARGIN, y, W - MARGIN, y + 40),
                   color=None, fill=(0.97, 0.97, 0.99))
    page.insert_text(fitz.Point(MARGIN + 8, y + 28),
                     str(total),
                     fontsize=32, color=g_colour, fontname="helv")
    page.insert_text(fitz.Point(MARGIN + 46, y + 28),
                     f"/ {max_s}",
                     fontsize=14, color=_LIGHT, fontname="helv")
    page.insert_text(fitz.Point(W - MARGIN - 30, y + 32),
                     grade,
                     fontsize=36, color=g_colour, fontname="helv")
    page.insert_text(fitz.Point(MARGIN + 100, y + 20),
                     evaluation.score_summary.performance_status,
                     fontsize=9, color=g_colour, fontname="helv")
    y += 48.0

    # ── Parameter breakdown table ─────────────────────────────────────────
    y = _draw_parameter_table(page, evaluation.parameter_breakdown, y, W, MARGIN)
    y += 8.0

    # ── Overall remarks ───────────────────────────────────────────────────
    if evaluation.overall_evaluation.summary_remarks and y < H - 80:
        page.insert_text(fitz.Point(MARGIN, y + 8),
                         "OVERALL REMARKS",
                         fontsize=7, color=_VIOLET, fontname="helv")
        y += 12.0
        remark = evaluation.overall_evaluation.summary_remarks
        y = _insert_wrapped_text(page, remark, MARGIN + 2, y,
                                  W - MARGIN - 2, fontsize=7,
                                  colour=_DARK, bg=(0.97, 0.95, 1.0))
        y += 8.0

    # ── Before You Resubmit ───────────────────────────────────────────────
    checklist = evaluation.overall_evaluation.actionable_resubmission_checklist
    if checklist and y < H - 50:
        # Dashed separator
        page.draw_line(fitz.Point(MARGIN, y), fitz.Point(W - MARGIN, y),
                       color=_LIGHT, width=0.4, dashes="[3 3]")
        y += 8.0
        page.insert_text(fitz.Point(MARGIN, y + 7),
                         "BEFORE YOU RESUBMIT",
                         fontsize=7.5, color=_DARK, fontname="helv")
        y += 14.0

        col_w  = (W - 2 * MARGIN - 8) / 2
        mid    = (len(checklist) + 1) // 2
        left   = checklist[:mid]
        right  = checklist[mid:]
        row_h  = 18.0
        base_y = y

        for i, item in enumerate(left):
            cy = base_y + i * row_h
            # Circle number badge
            page.draw_circle(fitz.Point(MARGIN + 6, cy + 5), 5,
                              color=None, fill=_VIOLET)
            page.insert_text(fitz.Point(MARGIN + 3.5, cy + 8),
                              str(i + 1),
                              fontsize=5, color=_WHITE, fontname="helv")
            _insert_wrapped_text(page, item[:90],
                                  MARGIN + 14, cy + 2,
                                  col_w - 14, fontsize=6.5, colour=_DARK)

        for j, item in enumerate(right):
            cy = base_y + j * row_h
            rx = MARGIN + col_w + 8
            page.draw_circle(fitz.Point(rx + 6, cy + 5), 5,
                              color=None, fill=_VIOLET)
            page.insert_text(fitz.Point(rx + 3.5, cy + 8),
                              str(mid + j + 1),
                              fontsize=5, color=_WHITE, fontname="helv")
            _insert_wrapped_text(page, item[:90],
                                  rx + 14, cy + 2,
                                  col_w - 14, fontsize=6.5, colour=_DARK)

    # ── Footer ────────────────────────────────────────────────────────────
    page.insert_text(fitz.Point(MARGIN, H - 10),
                     "theroundtableias.com",
                     fontsize=6, color=_LIGHT, fontname="helv")
    page.insert_text(fitz.Point(W - 120, H - 10),
                     "RoundtableIAS  ·  YouTube",
                     fontsize=6, color=_LIGHT, fontname="helv")


def _draw_parameter_table(
    page,
    params: list[ParameterBreakdown],
    y: float,
    W: float,
    MARGIN: float,
) -> float:
    """Draw the parameter rubric table. Returns updated y."""
    import fitz

    if not params:
        return y

    COL_PARAM  = (W - 2 * MARGIN) * 0.40
    COL_MAX    = (W - 2 * MARGIN) * 0.09
    COL_MARKS  = (W - 2 * MARGIN) * 0.10
    COL_REMARK = (W - 2 * MARGIN) * 0.41
    ROW_H      = 13.0

    # Header row
    page.draw_rect(fitz.Rect(MARGIN, y, W - MARGIN, y + ROW_H),
                   color=None, fill=_DARK)
    hx = MARGIN + 3
    for label, cx in [
        ("PARAMETER",        hx),
        ("MAX",              hx + COL_PARAM),
        ("MARKS",            hx + COL_PARAM + COL_MAX),
        ("EXAMINER'S REMARK", hx + COL_PARAM + COL_MAX + COL_MARKS),
    ]:
        page.insert_text(fitz.Point(cx, y + ROW_H - 4),
                         label, fontsize=6, color=_WHITE, fontname="helv")
    y += ROW_H

    for i, pb in enumerate(params):
        fill = _WHITE if i % 2 == 0 else (0.97, 0.97, 0.99)
        page.draw_rect(fitz.Rect(MARGIN, y, W - MARGIN, y + ROW_H),
                       color=None, fill=fill)

        pct_p  = pb.marks_obtained / pb.max_marks if pb.max_marks else 0
        s_col  = _GREEN if pct_p >= 0.75 else (_AMBER if pct_p >= 0.5 else _RED)
        rx     = MARGIN + 3

        page.insert_text(fitz.Point(rx, y + ROW_H - 4),
                         pb.parameter_name[:38],
                         fontsize=6, color=_DARK, fontname="helv")
        page.insert_text(fitz.Point(rx + COL_PARAM, y + ROW_H - 4),
                         str(pb.max_marks),
                         fontsize=6, color=_DARK, fontname="helv")
        page.insert_text(fitz.Point(rx + COL_PARAM + COL_MAX, y + ROW_H - 4),
                         str(pb.marks_obtained),
                         fontsize=7, color=s_col, fontname="helv")
        page.insert_text(
            fitz.Point(rx + COL_PARAM + COL_MAX + COL_MARKS, y + ROW_H - 4),
            pb.examiner_remark[:55],
            fontsize=6, color=_DARK, fontname="helv",
        )

        # Row border
        page.draw_line(fitz.Point(MARGIN, y + ROW_H),
                       fitz.Point(W - MARGIN, y + ROW_H),
                       color=_LIGHT, width=0.2)
        y += ROW_H

    # Total row
    total = sum(pb.marks_obtained for pb in params)
    max_t = sum(pb.max_marks for pb in params)
    pct   = total / max_t if max_t else 0
    g_col = _GREEN if pct >= 0.8 else _VIOLET if pct >= 0.6 else _AMBER if pct >= 0.4 else _RED

    page.draw_rect(fitz.Rect(MARGIN, y, W - MARGIN, y + ROW_H + 2),
                   color=None, fill=_DARK)
    page.insert_text(fitz.Point(MARGIN + 3, y + ROW_H - 2),
                     "TOTAL SCORE",
                     fontsize=7, color=_WHITE, fontname="helv")
    page.insert_text(fitz.Point(W - MARGIN - 55, y + ROW_H - 2),
                     f"{total} / {max_t}",
                     fontsize=10, color=g_col, fontname="helv")
    return y + ROW_H + 6


# ── Text helpers ──────────────────────────────────────────────────────────────

def _insert_wrapped_text(
    page,
    text: str,
    x: float, y: float,
    max_w: float,
    fontsize: float = 7,
    colour: tuple = _DARK,
    bg: tuple | None = None,
) -> float:
    """
    Insert word-wrapped text into the page.
    Returns the y coordinate after the last line.
    """
    import fitz

    chars_per_line = max(10, int(max_w / (fontsize * 0.52)))
    words  = text.split()
    lines  : list[str] = []
    current = ""
    for w in words:
        cand = f"{current} {w}".strip()
        if len(cand) <= chars_per_line:
            current = cand
        else:
            if current:
                lines.append(current)
            current = w
    if current:
        lines.append(current)

    LINE_H = fontsize * 1.4
    total_h = LINE_H * len(lines) + 4

    if bg:
        page.draw_rect(fitz.Rect(x - 2, y - 2, x + max_w + 2, y + total_h),
                       color=None, fill=bg)

    for i, line in enumerate(lines):
        page.insert_text(
            fitz.Point(x, y + fontsize + i * LINE_H),
            line, fontsize=fontsize, color=colour, fontname="helv",
        )

    return y + total_h


# ── Helpers ───────────────────────────────────────────────────────────────────

def _annotation_colour(ann: PageAnnotation) -> tuple:
    return {
        "PRAISE":          _GREEN,
        "CORRECTION":      _RED,
        "STRUCTURAL_NOTE": _VIOLET,
    }.get(ann.annotation_type, _BLUE)


def _annotation_symbol(ann: PageAnnotation) -> str:
    if ann.mark_symbol == "TICK"  or ann.annotation_type == "PRAISE":
        return "✓"
    if ann.mark_symbol == "CROSS" or ann.annotation_type == "CORRECTION":
        return "✗"
    return "•"


def _pil_to_jpeg_bytes(pil_img) -> bytes:
    buf = io.BytesIO()
    pil_img.convert("RGB").save(buf, format="JPEG", quality=90)
    return buf.getvalue()


# ── ReportLab fallback (when PyMuPDF is not installed) ───────────────────────

def _build_fallback_pdf(
    page_images: list,
    evaluation: EvaluationResult,
    question: str | None,
    exam_type: str,
    job_id: str,
) -> bytes:
    """
    Minimal fallback using ReportLab when PyMuPDF is not available.
    Just embeds the page images + a basic score sheet.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen.canvas import Canvas
    from reportlab.lib.utils import ImageReader

    buf = io.BytesIO()
    c   = Canvas(buf, pagesize=A4)
    W, H = A4

    for pil_img in page_images:
        img_buf = io.BytesIO()
        pil_img.convert("RGB").save(img_buf, format="JPEG", quality=88)
        img_buf.seek(0)
        c.drawImage(ImageReader(img_buf), 0, 0, width=W, height=H,
                    preserveAspectRatio=True)
        c.showPage()

    # Minimal score page
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, H - 60, "Evaluation Score Sheet")
    c.setFont("Helvetica", 12)
    c.drawString(50, H - 90,
                 f"Score: {evaluation.score_summary.total_score} / "
                 f"{evaluation.score_summary.max_score}  "
                 f"Grade: {evaluation.score_summary.grade}")
    c.drawString(50, H - 110, evaluation.score_summary.performance_status)
    y = H - 140
    for pb in evaluation.parameter_breakdown:
        c.setFont("Helvetica", 9)
        c.drawString(50, y,
                     f"{pb.parameter_name}: {pb.marks_obtained}/{pb.max_marks}"
                     f"  — {pb.examiner_remark[:60]}")
        y -= 14
        if y < 60:
            c.showPage()
            y = H - 60
    c.showPage()
    c.save()
    return buf.getvalue()
