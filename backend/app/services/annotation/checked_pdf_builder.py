"""
Builds the final teacher-checked PDF using PyMuPDF (fitz).

Pipeline per answer page:
  1. Embed original handwritten page image as background
  2. Draw right-margin panel (28% of page width)
  3. For each annotation: draw inline mark + margin comment box
  4. Add page footer

Final page: ANSWER SHEET EVALUATION score card.

Annotation type → ink mark:
  tick      → green  ✓  (left margin) + green underline
  cross     → red    ✗  (left margin) + wavy red underline
  circle    → red ellipse around text region
  underline → green straight underline
  comment   → violet margin box only

Falls back to ReportLab when PyMuPDF (fitz) is not installed.
"""
from __future__ import annotations

import io
from datetime import datetime, timezone

from app.models.domain.evaluation import (
    EvaluationResult, TeacherAnnotation, RubricItem,
)
from app.core.logging import get_logger

logger = get_logger(__name__)

# ── Colour palette (RGB 0–1) ──────────────────────────────────────────────────
_RED    = (0.86, 0.10, 0.10)
_GREEN  = (0.08, 0.63, 0.28)
_BLUE   = (0.15, 0.39, 0.92)
_VIOLET = (0.39, 0.13, 0.83)
_AMBER  = (0.85, 0.53, 0.04)
_DARK   = (0.06, 0.09, 0.16)
_LIGHT  = (0.72, 0.72, 0.78)
_WHITE  = (1.00, 1.00, 1.00)
_BG     = (0.97, 0.97, 0.99)

_MARGIN_RATIO   = 0.28   # right margin panel width as fraction of page
_MARGIN_PAD     = 5.0    # pt padding inside comment boxes
_BOX_MIN_H      = 20.0   # pt minimum comment box height
_LINE_H         = 9.0    # pt line height inside comment boxes
_BODY_TOP_PAD   = 60.0   # pt from top — where body text approximately starts
_PARA_HEIGHT    = 55.0   # pt estimated height per paragraph


def build_checked_pdf(
    page_images: list,          # list[PIL.Image.Image]
    evaluation: EvaluationResult,
    question: str | None,
    exam_type: str,
    job_id: str,
) -> bytes:
    """Build complete checked PDF. Returns raw PDF bytes."""
    try:
        import fitz
    except ImportError:
        logger.warning("pymupdf_not_installed_using_reportlab_fallback")
        return _build_fallback_pdf(page_images, evaluation, question, exam_type, job_id)

    doc = fitz.open()
    total = len(page_images)

    for idx, pil_img in enumerate(page_images):
        page_num = idx + 1
        img_bytes = _pil_to_jpeg(pil_img)
        annotations = evaluation.evaluation_summary.annotations_for_page(page_num)
        _render_answer_page(doc, img_bytes, annotations, page_num, total)

    _render_score_sheet(doc, evaluation, question, exam_type, job_id)

    pdf_bytes = doc.tobytes(garbage=4, deflate=True)
    doc.close()
    logger.info("checked_pdf_built", pages=total + 1,
                size_kb=len(pdf_bytes) // 1024)
    return pdf_bytes


def _render_answer_page(
    doc,
    img_bytes: bytes,
    annotations: list[TeacherAnnotation],
    page_num: int,
    total_pages: int,
) -> None:
    """Render one answer page with red-ink marks and margin comments."""
    import fitz

    W, H = 595.0, 842.0
    page = doc.new_page(width=W, height=H)

    margin_x = W * (1 - _MARGIN_RATIO)

    # ── Background: original handwritten image ────────────────────────────
    img_rect = fitz.Rect(0, 0, margin_x, H)
    page.insert_image(img_rect, stream=img_bytes, keep_proportion=True)

    # ── Right margin panel ────────────────────────────────────────────────
    page.draw_rect(fitz.Rect(margin_x, 0, W, H), color=None, fill=_BG)
    page.draw_line(fitz.Point(margin_x, 0), fitz.Point(margin_x, H),
                   color=_LIGHT, width=0.8)

    page.insert_text(fitz.Point(margin_x + 5, 14),
                     "Examiner's Notes",
                     fontsize=7, color=_VIOLET, fontname="helv")
    page.draw_line(fitz.Point(margin_x + 3, 18),
                   fitz.Point(W - 3, 18),
                   color=_LIGHT, width=0.4)

    # ── Draw annotations ─────────────────────────────────────────────────
    sorted_ann = sorted(annotations, key=lambda a: (a.paragraph, a.sentence or 0))
    next_margin_y = 24.0

    for ann in sorted_ann:
        y_pt = _annotation_y(ann, H)
        colour = _ann_colour(ann.annotation_type)
        _draw_inline_mark(page, ann, y_pt, margin_x, colour)
        next_margin_y = _draw_margin_comment(
            page, ann, margin_x, next_margin_y, W, H, colour
        )

    # ── Page footer ───────────────────────────────────────────────────────
    page.insert_text(fitz.Point(8, H - 8),
                     f"Page {page_num} of {total_pages + 1}",
                     fontsize=6, color=_LIGHT, fontname="helv")
    page.insert_text(fitz.Point(W - 130, H - 8),
                     "AI Evaluator — Checked Answer",
                     fontsize=6, color=_LIGHT, fontname="helv")


def _annotation_y(ann: TeacherAnnotation, page_height: float) -> float:
    """
    Convert logical paragraph+sentence position to a y-coordinate (pt).
    Assumes body text starts at _BODY_TOP_PAD, each paragraph ~_PARA_HEIGHT pt.
    """
    para_y = _BODY_TOP_PAD + (ann.paragraph - 1) * _PARA_HEIGHT
    if ann.sentence:
        sentence_offset = (ann.sentence - 1) * 14.0  # ~14pt per line
        para_y += sentence_offset
    return min(para_y, page_height - 20)


def _ann_colour(ann_type: str) -> tuple:
    return {
        "tick":      _GREEN,
        "underline": _GREEN,
        "cross":     _RED,
        "circle":    _RED,
        "comment":   _VIOLET,
    }.get(ann_type, _BLUE)


def _draw_inline_mark(
    page, ann: TeacherAnnotation, y: float,
    margin_x: float, colour: tuple,
) -> None:
    """Draw the inline ink mark on the answer body area."""
    import fitz

    left_x  = 6.0
    text_x  = 28.0
    text_end = margin_x - 18.0

    if ann.annotation_type == "tick":
        page.insert_text(fitz.Point(left_x, y), "✓",
                          fontsize=11, color=_GREEN, fontname="helv")
        page.draw_line(fitz.Point(text_x, y + 3),
                       fitz.Point(text_end * 0.7, y + 3),
                       color=_GREEN, width=1.1)

    elif ann.annotation_type == "cross":
        page.insert_text(fitz.Point(left_x, y), "✗",
                          fontsize=11, color=_RED, fontname="helv")
        _draw_wavy(page, text_x, y + 3, text_end * 0.6, _RED)

    elif ann.annotation_type == "circle":
        page.draw_oval(fitz.Rect(text_x, y - 7, text_x + 70, y + 5),
                       color=_RED, width=1.0)

    elif ann.annotation_type == "underline":
        page.draw_line(fitz.Point(text_x, y + 3),
                       fitz.Point(text_end * 0.75, y + 3),
                       color=_GREEN, width=1.2)

    # Arrow pointing to margin
    page.draw_line(fitz.Point(margin_x - 15, y),
                   fitz.Point(margin_x - 3, y),
                   color=colour, width=0.5)


def _draw_margin_comment(
    page, ann: TeacherAnnotation, margin_x: float,
    next_y: float, W: float, H: float, colour: tuple,
) -> float:
    """Draw coloured comment box in the right margin. Returns updated next_y."""
    import fitz

    BG_COLOURS = {
        "tick":      (0.90, 0.98, 0.93),
        "underline": (0.90, 0.98, 0.93),
        "cross":     (0.99, 0.92, 0.92),
        "circle":    (0.99, 0.92, 0.92),
        "comment":   (0.93, 0.92, 0.99),
    }
    bg = BG_COLOURS.get(ann.annotation_type, (0.96, 0.96, 1.0))

    ann_y = _annotation_y(ann, H)
    box_y = max(next_y, ann_y - 6)
    box_y = min(box_y, H - _BOX_MIN_H - 4)

    text  = ann.comment[:40]
    words = text.split()
    lines: list[str] = []
    cur   = ""
    for w in words:
        cand = f"{cur} {w}".strip()
        lines.append(cur := cand) if len(cand) <= 24 else (
            lines.append(cur) or setattr(ann, "__tmp", None),
            lines.pop(),
            lines.append(cur),
            [lines.append(w) for _ in []] or setattr(ann, "__tmp", None)
        )
    # simple word wrap
    lines = []
    cur   = ""
    for w in words:
        cand = f"{cur} {w}".strip()
        if len(cand) <= 24:
            cur = cand
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    lines = lines or [text]

    box_h = max(_BOX_MIN_H, _MARGIN_PAD * 2 + _LINE_H * len(lines))
    x1 = margin_x + 3
    x2 = W - 3

    page.draw_rect(fitz.Rect(x1, box_y, x2, box_y + box_h),
                   color=None, fill=bg)
    page.draw_rect(fitz.Rect(x1, box_y, x1 + 3, box_y + box_h),
                   color=None, fill=colour)
    for i, ln in enumerate(lines):
        page.insert_text(
            fitz.Point(x1 + 6, box_y + _MARGIN_PAD + _LINE_H * (i + 0.8)),
            ln, fontsize=6, color=_DARK, fontname="helv"
        )

    return box_y + box_h + 4


def _draw_wavy(page, x1: float, y: float, x2: float, colour: tuple) -> None:
    """Draw a wavy underline to indicate errors."""
    import fitz
    amp, period = 2.5, 8.0
    x, toggle = x1, 1
    while x < x2 - period:
        nx = min(x + period, x2)
        page.draw_line(fitz.Point(x, y), fitz.Point(nx, y + amp * toggle),
                       color=colour, width=1.0)
        toggle = -toggle
        x = nx


# ── Final Score Sheet ─────────────────────────────────────────────────────────

def _render_score_sheet(
    doc,
    evaluation: EvaluationResult,
    question: str | None,
    exam_type: str,
    job_id: str,
) -> None:
    """Append the professional ANSWER SHEET EVALUATION score sheet page."""
    import fitz

    es   = evaluation.evaluation_summary
    W, H = 595.0, 842.0
    M    = 30.0   # left/right margin
    page = doc.new_page(width=W, height=H)
    now  = datetime.now(tz=timezone.utc).strftime("%d %b %Y")

    pct  = es.total_marks / es.max_marks if es.max_marks else 0
    gc   = (_GREEN if pct >= 0.8 else _VIOLET if pct >= 0.6
            else _AMBER if pct >= 0.4 else _RED)

    # ── Top header bar ────────────────────────────────────────────────────
    page.draw_rect(fitz.Rect(0, 0, W, 44), color=None, fill=_DARK)
    page.insert_text(fitz.Point(M, 16),
                     "════════════════════════════════════════",
                     fontsize=7, color=_LIGHT, fontname="helv")
    page.insert_text(fitz.Point(M, 28),
                     "    ANSWER SHEET EVALUATION",
                     fontsize=12, color=_WHITE, fontname="helv")
    page.insert_text(fitz.Point(M, 40),
                     "════════════════════════════════════════",
                     fontsize=7, color=_LIGHT, fontname="helv")

    y = 58.0

    # ── Student info block ────────────────────────────────────────────────
    page.draw_rect(fitz.Rect(M, y, W - M, y + 36),
                   color=None, fill=(0.94, 0.94, 0.98))
    page.insert_text(fitz.Point(M + 6, y + 12),
                     f"Student: {es.student_name or 'N/A'}",
                     fontsize=9, color=_DARK, fontname="helv")
    page.insert_text(fitz.Point(M + 6, y + 24),
                     f"Subject: {es.subject or exam_type}    "
                     f"Date: {now}    Pages: {es.total_pages}",
                     fontsize=8, color=_DARK, fontname="helv")
    y += 42.0

    # ── Marks breakdown table ─────────────────────────────────────────────
    y = _draw_rubric_table(page, es.rubric, y, W, M)
    y += 4.0

    # ── Total / Grade hero ────────────────────────────────────────────────
    page.draw_rect(fitz.Rect(M, y, W - M, y + 32),
                   color=None, fill=_DARK)
    page.insert_text(fitz.Point(M + 8, y + 20),
                     "Total",
                     fontsize=9, color=_WHITE, fontname="helv")
    page.insert_text(fitz.Point(M + 50, y + 22),
                     f"{es.total_marks} / {es.max_marks}",
                     fontsize=14, color=gc, fontname="helv")
    page.insert_text(fitz.Point(W - M - 60, y + 22),
                     f"Grade: {es.grade}",
                     fontsize=13, color=gc, fontname="helv")
    page.insert_text(fitz.Point(W // 2 - 40, y + 22),
                     es.performance_level,
                     fontsize=9, color=_AMBER, fontname="helv")
    y += 38.0

    # ── Strengths ─────────────────────────────────────────────────────────
    if es.strengths:
        y = _section_header(page, "Strengths", y, M, W, _GREEN)
        for s in es.strengths[:4]:
            page.insert_text(fitz.Point(M + 8, y + 10),
                             f"✓  {s[:80]}", fontsize=8, color=_DARK, fontname="helv")
            y += 13.0
        y += 4.0

    # ── Needs Improvement ─────────────────────────────────────────────────
    if es.weaknesses:
        y = _section_header(page, "Needs Improvement", y, M, W, _RED)
        for w in es.weaknesses[:4]:
            page.insert_text(fitz.Point(M + 8, y + 10),
                             f"•  {w[:80]}", fontsize=8, color=_DARK, fontname="helv")
            y += 13.0
        y += 4.0

    # ── Teacher Remarks ───────────────────────────────────────────────────
    if es.remarks and y < H - 80:
        y = _section_header(page, "Teacher Remarks", y, M, W, _VIOLET)
        page.draw_rect(fitz.Rect(M, y, W - M, y + 2), color=None, fill=_LIGHT)
        y += 6.0
        y = _wrapped_text(page, es.remarks, M + 6, y, W - M - 6,
                          fontsize=8, colour=_DARK)
        y += 8.0

    # ── Teacher signature ─────────────────────────────────────────────────
    if y < H - 40:
        page.draw_line(fitz.Point(W - M - 100, y + 4),
                       fitz.Point(W - M, y + 4),
                       color=_LIGHT, width=0.5)
        page.insert_text(fitz.Point(W - M - 100, y + 14),
                         "AI Evaluator",
                         fontsize=7, color=_LIGHT, fontname="helv")

    # ── Footer ────────────────────────────────────────────────────────────
    page.insert_text(fitz.Point(M, H - 10),
                     "AI Answer Sheet Evaluation System",
                     fontsize=6, color=_LIGHT, fontname="helv")
    page.insert_text(fitz.Point(W - M - 80, H - 10),
                     f"Job: {job_id[:12]}",
                     fontsize=6, color=_LIGHT, fontname="helv")


def _draw_rubric_table(
    page, rubric: dict[str, RubricItem],
    y: float, W: float, M: float,
) -> float:
    """Draw the marks breakdown table. Returns updated y."""
    import fitz

    ROW_H  = 13.0
    COL_P  = (W - 2 * M) * 0.44
    COL_MX = (W - 2 * M) * 0.12
    COL_MK = (W - 2 * M) * 0.12
    COL_RK = (W - 2 * M) * 0.32

    # Table header row
    page.draw_rect(fitz.Rect(M, y, W - M, y + ROW_H), color=None, fill=_DARK)
    rx = M + 3
    for label, cx in [("PARAMETER", rx), ("MAX", rx + COL_P),
                      ("MARKS", rx + COL_P + COL_MX),
                      ("REMARKS", rx + COL_P + COL_MX + COL_MK)]:
        page.insert_text(fitz.Point(cx, y + ROW_H - 3),
                         label, fontsize=5.5, color=_WHITE, fontname="helv")
    y += ROW_H

    PARAM_ICONS = {
        "introduction": "✎", "content": "📄", "grammar": "G",
        "vocabulary": "V", "presentation": "P", "handwriting": "✍",
        "conclusion": "C", "creativity": "★", "flow": "↻",
    }

    for i, (key, item) in enumerate(rubric.items()):
        fill = _WHITE if i % 2 == 0 else (0.97, 0.97, 0.99)
        page.draw_rect(fitz.Rect(M, y, W - M, y + ROW_H), color=None, fill=fill)
        pct_p = item.marks / item.max if item.max else 0
        sc    = _GREEN if pct_p >= 0.75 else (_AMBER if pct_p >= 0.5 else _RED)
        icon  = PARAM_ICONS.get(key, "•")
        label = f"{icon}  {key.capitalize()}"
        page.insert_text(fitz.Point(M + 3, y + ROW_H - 3),
                         label[:28], fontsize=6.5, color=_DARK, fontname="helv")
        page.insert_text(fitz.Point(M + 3 + COL_P, y + ROW_H - 3),
                         str(item.max), fontsize=6.5, color=_DARK, fontname="helv")
        page.insert_text(fitz.Point(M + 3 + COL_P + COL_MX, y + ROW_H - 3),
                         str(item.marks), fontsize=7.5, color=sc, fontname="helv")
        remark = item.remark[:42] if item.remark else ""
        page.insert_text(fitz.Point(M + 3 + COL_P + COL_MX + COL_MK, y + ROW_H - 3),
                         remark, fontsize=5.5, color=_DARK, fontname="helv")
        page.draw_line(fitz.Point(M, y + ROW_H),
                       fitz.Point(W - M, y + ROW_H),
                       color=_LIGHT, width=0.2)
        y += ROW_H

    return y


def _section_header(
    page, title: str, y: float, M: float, W: float, colour: tuple,
) -> float:
    """Draw a coloured section header. Returns updated y."""
    import fitz
    page.draw_rect(fitz.Rect(M, y, W - M, y + 16),
                   color=None, fill=colour)
    page.insert_text(fitz.Point(M + 5, y + 11),
                     title, fontsize=8, color=_WHITE, fontname="helv")
    return y + 20.0


def _wrapped_text(
    page, text: str, x: float, y: float, max_w: float,
    fontsize: float = 8, colour: tuple = _DARK,
) -> float:
    """Insert word-wrapped text. Returns y after last line."""
    import fitz
    chars = max(10, int(max_w / (fontsize * 0.52)))
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        cand = f"{cur} {w}".strip()
        if len(cand) <= chars:
            cur = cand
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    lh = fontsize * 1.4
    for i, ln in enumerate(lines):
        page.insert_text(fitz.Point(x, y + fontsize + i * lh),
                         ln, fontsize=fontsize, color=colour, fontname="helv")
    return y + fontsize + len(lines) * lh


def _pil_to_jpeg(pil_img) -> bytes:
    buf = io.BytesIO()
    pil_img.convert("RGB").save(buf, format="JPEG", quality=90)
    return buf.getvalue()


# ── ReportLab fallback ────────────────────────────────────────────────────────

def _build_fallback_pdf(
    page_images: list,
    evaluation: EvaluationResult,
    question: str | None,
    exam_type: str,
    job_id: str,
) -> bytes:
    """Minimal fallback using ReportLab when PyMuPDF is unavailable."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen.canvas import Canvas
    from reportlab.lib.utils import ImageReader

    buf = io.BytesIO()
    c   = Canvas(buf, pagesize=A4)
    W, H = A4

    for pil_img in page_images:
        ib = io.BytesIO()
        pil_img.convert("RGB").save(ib, format="JPEG", quality=88)
        ib.seek(0)
        c.drawImage(ImageReader(ib), 0, 0, width=W, height=H,
                    preserveAspectRatio=True)
        c.showPage()

    es = evaluation.evaluation_summary
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, H - 60, "ANSWER SHEET EVALUATION")
    c.setFont("Helvetica", 10)
    c.drawString(40, H - 90,  f"Student: {es.student_name or 'N/A'}")
    c.drawString(40, H - 105, f"Subject: {es.subject or exam_type}")
    c.drawString(40, H - 120, f"Total Marks: {es.total_marks} / {es.max_marks}")
    c.drawString(40, H - 135, f"Grade: {es.grade}  —  {es.performance_level}")
    y = H - 165
    for key, item in es.rubric.items():
        c.setFont("Helvetica", 9)
        c.drawString(40, y, f"{key.capitalize()}: {item.marks}/{item.max}")
        y -= 14
        if y < 60:
            c.showPage()
            y = H - 60
    if es.remarks:
        c.setFont("Helvetica-Oblique", 9)
        c.drawString(40, y - 10, f"Remarks: {es.remarks[:100]}")
    c.showPage()
    c.save()
    return buf.getvalue()


def build_checked_pdf(
    page_images: list,
    evaluation: EvaluationResult,
    question: str | None,
    exam_type: str,
    job_id: str,
) -> bytes:
    """Build complete checked PDF. Returns raw PDF bytes."""
    try:
        import fitz
    except ImportError:
        logger.warning("pymupdf_not_installed_using_reportlab_fallback")
        return _build_fallback_pdf(page_images, evaluation, question, exam_type, job_id)

    doc = fitz.open()
    total = len(page_images)

    for idx, pil_img in enumerate(page_images):
        page_num  = idx + 1
        img_bytes = _pil_to_jpeg(pil_img)
        anns      = evaluation.evaluation_summary.annotations_for_page(page_num)
        _render_answer_page(doc, img_bytes, anns, page_num, total)

    _render_score_sheet(doc, evaluation, question, exam_type, job_id)

    pdf_bytes = doc.tobytes(garbage=4, deflate=True)
    doc.close()
    logger.info("checked_pdf_built", pages=total + 1,
                size_kb=len(pdf_bytes) // 1024)
    return pdf_bytes


def _render_answer_page(
    doc, img_bytes: bytes, annotations: list[TeacherAnnotation],
    page_num: int, total_pages: int,
) -> None:
    import fitz
    W, H = 595.0, 842.0
    margin_x = W * (1 - _MARGIN_RATIO)
    page = doc.new_page(width=W, height=H)

    # Original handwritten image as background (left part only)
    page.insert_image(fitz.Rect(0, 0, margin_x, H), stream=img_bytes,
                      keep_proportion=True)

    # Right margin panel
    page.draw_rect(fitz.Rect(margin_x, 0, W, H), color=None, fill=_BG)
    page.draw_line(fitz.Point(margin_x, 0), fitz.Point(margin_x, H),
                   color=_LIGHT, width=0.8)
    page.insert_text(fitz.Point(margin_x + 5, 14), "Examiner's Notes",
                     fontsize=7, color=_VIOLET, fontname="helv")
    page.draw_line(fitz.Point(margin_x + 3, 18), fitz.Point(W - 3, 18),
                   color=_LIGHT, width=0.4)

    sorted_ann = sorted(annotations, key=lambda a: (a.paragraph, a.sentence or 0))
    next_y = 24.0
    for ann in sorted_ann:
        y_pt   = _annotation_y(ann, H)
        colour = _ann_colour(ann.annotation_type)
        _draw_inline_mark(page, ann, y_pt, margin_x, colour)
        next_y = _draw_margin_box(page, ann, margin_x, next_y, W, H, colour)

    page.insert_text(fitz.Point(8, H - 8),
                     f"Page {page_num} of {total_pages + 1}",
                     fontsize=6, color=_LIGHT, fontname="helv")
    page.insert_text(fitz.Point(W - 130, H - 8), "AI Evaluator — Checked",
                     fontsize=6, color=_LIGHT, fontname="helv")


def _annotation_y(ann: TeacherAnnotation, H: float) -> float:
    y = _BODY_TOP_PAD + (ann.paragraph - 1) * _PARA_HEIGHT
    if ann.sentence:
        y += (ann.sentence - 1) * 14.0
    return min(y, H - 20.0)


def _ann_colour(t: str) -> tuple:
    return {"tick": _GREEN, "underline": _GREEN,
            "cross": _RED, "circle": _RED,
            "comment": _VIOLET}.get(t, _BLUE)


def _draw_inline_mark(
    page, ann: TeacherAnnotation, y: float,
    margin_x: float, colour: tuple,
) -> None:
    import fitz
    lx, tx, te = 6.0, 28.0, margin_x - 18.0

    if ann.annotation_type == "tick":
        page.insert_text(fitz.Point(lx, y), "✓",
                         fontsize=11, color=_GREEN, fontname="helv")
        page.draw_line(fitz.Point(tx, y + 3), fitz.Point(te * 0.7, y + 3),
                       color=_GREEN, width=1.1)
    elif ann.annotation_type == "cross":
        page.insert_text(fitz.Point(lx, y), "✗",
                         fontsize=11, color=_RED, fontname="helv")
        _wavy(page, tx, y + 3, te * 0.6, _RED)
    elif ann.annotation_type == "circle":
        page.draw_oval(fitz.Rect(tx, y - 7, tx + 70, y + 5),
                       color=_RED, width=1.0)
    elif ann.annotation_type == "underline":
        page.draw_line(fitz.Point(tx, y + 3), fitz.Point(te * 0.75, y + 3),
                       color=_GREEN, width=1.2)

    # Arrow to margin
    page.draw_line(fitz.Point(margin_x - 15, y), fitz.Point(margin_x - 3, y),
                   color=colour, width=0.5)


def _draw_margin_box(
    page, ann: TeacherAnnotation, margin_x: float,
    next_y: float, W: float, H: float, colour: tuple,
) -> float:
    import fitz
    BG = {"tick": (0.90, 0.98, 0.93), "underline": (0.90, 0.98, 0.93),
          "cross": (0.99, 0.92, 0.92), "circle": (0.99, 0.92, 0.92),
          "comment": (0.93, 0.92, 0.99)}.get(ann.annotation_type, (0.96, 0.96, 1.0))

    ann_y = _annotation_y(ann, H)
    by    = max(next_y, ann_y - 6)
    by    = min(by, H - _BOX_MIN_H - 4)

    words = ann.comment[:40].split()
    lines, cur = [], ""
    for w in words:
        cand = f"{cur} {w}".strip()
        if len(cand) <= 24:
            cur = cand
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    lines = lines or [ann.comment[:24]]

    bh = max(_BOX_MIN_H, _MARGIN_PAD * 2 + _LINE_H * len(lines))
    x1, x2 = margin_x + 3, W - 3
    page.draw_rect(fitz.Rect(x1, by, x2, by + bh), color=None, fill=BG)
    page.draw_rect(fitz.Rect(x1, by, x1 + 3, by + bh), color=None, fill=colour)
    for i, ln in enumerate(lines):
        page.insert_text(
            fitz.Point(x1 + 6, by + _MARGIN_PAD + _LINE_H * (i + 0.8)),
            ln, fontsize=6, color=_DARK, fontname="helv"
        )
    return by + bh + 4


def _wavy(page, x1: float, y: float, x2: float, colour: tuple) -> None:
    import fitz
    x, t = x1, 1
    while x < x2 - 8:
        nx = min(x + 8, x2)
        page.draw_line(fitz.Point(x, y), fitz.Point(nx, y + 2.5 * t),
                       color=colour, width=1.0)
        t, x = -t, nx


def _render_score_sheet(
    doc, evaluation: EvaluationResult,
    question: str | None, exam_type: str, job_id: str,
) -> None:
    import fitz
    es   = evaluation.evaluation_summary
    W, H = 595.0, 842.0
    M    = 30.0
    page = doc.new_page(width=W, height=H)
    now  = datetime.now(tz=timezone.utc).strftime("%d %b %Y")

    pct = es.total_marks / es.max_marks if es.max_marks else 0
    gc  = (_GREEN if pct >= 0.8 else _VIOLET if pct >= 0.6
           else _AMBER if pct >= 0.4 else _RED)

    # Header bar
    page.draw_rect(fitz.Rect(0, 0, W, 44), color=None, fill=_DARK)
    page.insert_text(fitz.Point(M, 16),
                     "================================",
                     fontsize=7, color=_LIGHT, fontname="helv")
    page.insert_text(fitz.Point(M, 28),
                     "    ANSWER SHEET EVALUATION",
                     fontsize=12, color=_WHITE, fontname="helv")
    page.insert_text(fitz.Point(M, 40),
                     "================================",
                     fontsize=7, color=_LIGHT, fontname="helv")
    y = 58.0

    # Student info
    page.draw_rect(fitz.Rect(M, y, W - M, y + 36), color=None, fill=(0.94, 0.94, 0.98))
    page.insert_text(fitz.Point(M + 6, y + 12),
                     f"Student: {es.student_name or 'N/A'}",
                     fontsize=9, color=_DARK, fontname="helv")
    page.insert_text(fitz.Point(M + 6, y + 24),
                     f"Subject: {es.subject or exam_type}"
                     f"    Date: {now}    Pages: {es.total_pages}",
                     fontsize=8, color=_DARK, fontname="helv")
    y += 42.0

    # Rubric table
    y = _rubric_table(page, es.rubric, y, W, M)
    y += 4.0

    # Total / Grade
    page.draw_rect(fitz.Rect(M, y, W - M, y + 32), color=None, fill=_DARK)
    page.insert_text(fitz.Point(M + 8, y + 20), "Total",
                     fontsize=9, color=_WHITE, fontname="helv")
    page.insert_text(fitz.Point(M + 50, y + 22),
                     f"{es.total_marks} / {es.max_marks}",
                     fontsize=14, color=gc, fontname="helv")
    page.insert_text(fitz.Point(W - M - 65, y + 22),
                     f"Grade: {es.grade}",
                     fontsize=13, color=gc, fontname="helv")
    page.insert_text(fitz.Point(W // 2 - 40, y + 22),
                     es.performance_level,
                     fontsize=9, color=_AMBER, fontname="helv")
    y += 38.0

    # Strengths
    if es.strengths:
        y = _sh(page, "Strengths", y, M, W, _GREEN)
        for s in es.strengths[:4]:
            page.insert_text(fitz.Point(M + 8, y + 10),
                             f"✓  {s[:80]}", fontsize=8, color=_DARK, fontname="helv")
            y += 13.0
        y += 4.0

    # Needs Improvement
    if es.weaknesses:
        y = _sh(page, "Needs Improvement", y, M, W, _RED)
        for w in es.weaknesses[:4]:
            page.insert_text(fitz.Point(M + 8, y + 10),
                             f"•  {w[:80]}", fontsize=8, color=_DARK, fontname="helv")
            y += 13.0
        y += 4.0

    # Teacher Remarks
    if es.remarks and y < H - 80:
        y = _sh(page, "Teacher Remarks", y, M, W, _VIOLET)
        y = _wt(page, es.remarks, M + 6, y, W - M - 6, fontsize=8, colour=_DARK)
        y += 8.0

    # Signature line
    if y < H - 40:
        page.draw_line(fitz.Point(W - M - 100, y + 4),
                       fitz.Point(W - M, y + 4), color=_LIGHT, width=0.5)
        page.insert_text(fitz.Point(W - M - 100, y + 14),
                         "AI Evaluator", fontsize=7, color=_LIGHT, fontname="helv")

    # Footer
    page.insert_text(fitz.Point(M, H - 10), "AI Answer Sheet Evaluation System",
                     fontsize=6, color=_LIGHT, fontname="helv")
    page.insert_text(fitz.Point(W - M - 80, H - 10), f"Job: {job_id[:12]}",
                     fontsize=6, color=_LIGHT, fontname="helv")


def _rubric_table(page, rubric: dict[str, RubricItem],
                  y: float, W: float, M: float) -> float:
    import fitz
    RH = 13.0
    CP = (W - 2 * M) * 0.44
    CM = (W - 2 * M) * 0.12
    CK = (W - 2 * M) * 0.12
    CR = (W - 2 * M) * 0.32

    # Header
    page.draw_rect(fitz.Rect(M, y, W - M, y + RH), color=None, fill=_DARK)
    rx = M + 3
    for lbl, cx in [("PARAMETER", rx), ("MAX", rx + CP),
                    ("MARKS", rx + CP + CM), ("REMARKS", rx + CP + CM + CK)]:
        page.insert_text(fitz.Point(cx, y + RH - 3), lbl,
                         fontsize=5.5, color=_WHITE, fontname="helv")
    y += RH

    ICONS = {"introduction": "Intro", "content": "Content", "grammar": "Grammar",
             "vocabulary": "Vocab", "presentation": "Present", "handwriting": "Writing",
             "conclusion": "Concl.", "creativity": "Creativ.", "flow": "Flow"}

    for i, (key, item) in enumerate(rubric.items()):
        fill = _WHITE if i % 2 == 0 else (0.97, 0.97, 0.99)
        page.draw_rect(fitz.Rect(M, y, W - M, y + RH), color=None, fill=fill)
        pct_p = item.marks / item.max if item.max else 0
        sc    = _GREEN if pct_p >= 0.75 else (_AMBER if pct_p >= 0.5 else _RED)
        page.insert_text(fitz.Point(M + 3, y + RH - 3),
                         ICONS.get(key, key.capitalize())[:22],
                         fontsize=6.5, color=_DARK, fontname="helv")
        page.insert_text(fitz.Point(M + 3 + CP, y + RH - 3),
                         str(item.max), fontsize=6.5, color=_DARK, fontname="helv")
        page.insert_text(fitz.Point(M + 3 + CP + CM, y + RH - 3),
                         str(item.marks), fontsize=7.5, color=sc, fontname="helv")
        if item.remark:
            page.insert_text(fitz.Point(M + 3 + CP + CM + CK, y + RH - 3),
                             item.remark[:42], fontsize=5.5, color=_DARK, fontname="helv")
        page.draw_line(fitz.Point(M, y + RH), fitz.Point(W - M, y + RH),
                       color=_LIGHT, width=0.2)
        y += RH
    return y


def _sh(page, title: str, y: float, M: float, W: float, colour: tuple) -> float:
    import fitz
    page.draw_rect(fitz.Rect(M, y, W - M, y + 16), color=None, fill=colour)
    page.insert_text(fitz.Point(M + 5, y + 11), title,
                     fontsize=8, color=_WHITE, fontname="helv")
    return y + 20.0


def _wt(page, text: str, x: float, y: float, max_w: float,
        fontsize: float = 8, colour: tuple = _DARK) -> float:
    import fitz
    chars = max(10, int(max_w / (fontsize * 0.52)))
    words = text.split()
    lines, cur = [], ""
    for w in words:
        cand = f"{cur} {w}".strip()
        if len(cand) <= chars:
            cur = cand
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    lh = fontsize * 1.4
    for i, ln in enumerate(lines):
        page.insert_text(fitz.Point(x, y + fontsize + i * lh),
                         ln, fontsize=fontsize, color=colour, fontname="helv")
    return y + fontsize + len(lines) * lh


def _pil_to_jpeg(img) -> bytes:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def _build_fallback_pdf(
    page_images: list, evaluation: EvaluationResult,
    question: str | None, exam_type: str, job_id: str,
) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen.canvas import Canvas
    from reportlab.lib.utils import ImageReader
    buf = io.BytesIO()
    c   = Canvas(buf, pagesize=A4)
    W, H = A4
    for pil_img in page_images:
        ib = io.BytesIO()
        pil_img.convert("RGB").save(ib, format="JPEG", quality=88)
        ib.seek(0)
        c.drawImage(ImageReader(ib), 0, 0, width=W, height=H,
                    preserveAspectRatio=True)
        c.showPage()
    es = evaluation.evaluation_summary
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, H - 60, "ANSWER SHEET EVALUATION")
    c.setFont("Helvetica", 10)
    c.drawString(40, H - 85,  f"Total: {es.total_marks}/{es.max_marks}  Grade: {es.grade}")
    y = H - 110
    for key, item in es.rubric.items():
        c.drawString(40, y, f"{key}: {item.marks}/{item.max}")
        y -= 14
        if y < 60:
            c.showPage(); y = H - 60
    c.showPage()
    c.save()
    return buf.getvalue()
