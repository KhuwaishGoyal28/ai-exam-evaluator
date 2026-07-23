"""
Builds a "checked PDF" — original answer pages with ink marks and margin notes,
plus a final summary score sheet page.

Single responsibility: original pages + evaluation → checked PDF bytes.

Layout per answer page:
  - Original answer page (as background image)
  - Red/green ink marks overlaid (tick, cross, wavy underlines)
  - Right margin panel with comment boxes (coloured by sentiment)
  - Page footer

Final page: summary score sheet.
  - Standard exams  → 5-parameter table
  - Essay exam      → 12-parameter table matching the Roundtable IAS sheet style
"""
from __future__ import annotations

import io
from PIL import Image
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas

from app.models.domain.evaluation import EvaluationResult, AnnotationComment
from app.core.logging import get_logger
from .ink_marker import draw_ink_marks
from .paragraph_locator import compute_paragraph_y_positions

logger = get_logger(__name__)

_MARGIN_RATIO = 0.30
_RED    = (0.86, 0.15, 0.15)
_GREEN  = (0.09, 0.64, 0.29)
_BLUE   = (0.15, 0.39, 0.92)
_DARK   = (0.06, 0.09, 0.16)
_LIGHT  = (0.58, 0.64, 0.72)
_VIOLET = (0.39, 0.13, 0.83)
_AMBER  = (0.85, 0.53, 0.04)


def build_checked_pdf(
    page_images: list[Image.Image],
    evaluation: EvaluationResult,
    question: str | None,
    exam_type: str,
    job_id: str,
) -> bytes:
    """Build a complete checked PDF. Returns raw PDF bytes."""
    buf = io.BytesIO()
    comments = evaluation.annotation_comments
    pages_comments = _distribute_comments(comments, len(page_images))

    c = Canvas(buf, pagesize=A4)
    W, H = A4

    for page_num, (page_img, page_comments) in enumerate(
        zip(page_images, pages_comments)
    ):
        _render_checked_page(
            canvas=c, page_img=page_img, page_comments=page_comments,
            page_num=page_num, total_pages=len(page_images),
            evaluation=evaluation, W=W, H=H,
        )
        c.showPage()

    # Final summary page
    if evaluation.is_essay:
        _render_essay_summary_page(c, evaluation, question, exam_type, job_id, W, H)
    else:
        _render_standard_summary_page(c, evaluation, question, exam_type, job_id, W, H)
    c.showPage()

    c.save()
    pdf_bytes = buf.getvalue()
    logger.info("checked_pdf_built", pages=len(page_images) + 1, size_bytes=len(pdf_bytes))
    return pdf_bytes


def _render_checked_page(
    canvas: Canvas, page_img: Image.Image,
    page_comments: list[AnnotationComment],
    page_num: int, total_pages: int,
    evaluation: EvaluationResult, W: float, H: float,
) -> None:
    """Render one answer page with ink marks and margin notes."""
    margin_w = W * _MARGIN_RATIO
    answer_w = W - margin_w

    y_positions = compute_paragraph_y_positions(
        image_height=page_img.height,
        num_paragraphs=max(len(page_comments), 1),
    )
    marked_img = draw_ink_marks(page_img, page_comments, y_positions, page_img.width)

    canvas.drawImage(
        _pil_to_reportlab(marked_img), 0, 0,
        width=answer_w, height=H,
        preserveAspectRatio=True, anchor="nw",
    )

    # Margin panel background
    canvas.setFillColorRGB(0.97, 0.97, 0.99)
    canvas.rect(answer_w, 0, margin_w, H, fill=1, stroke=0)
    canvas.setStrokeColorRGB(*_LIGHT)
    canvas.setLineWidth(1)
    canvas.line(answer_w, 0, answer_w, H)

    # Margin header
    canvas.setFillColorRGB(*_VIOLET)
    canvas.setFont("Helvetica-Bold", 8)
    canvas.drawString(answer_w + 6, H - 18, "Examiner's Notes")
    canvas.setStrokeColorRGB(*_LIGHT)
    canvas.setLineWidth(0.5)
    canvas.line(answer_w + 4, H - 22, W - 4, H - 22)

    _draw_margin_comments(canvas, page_comments, y_positions, answer_w, margin_w, H)
    _draw_page_footer(canvas, page_num, total_pages, W)


def _draw_margin_comments(
    canvas: Canvas, comments: list[AnnotationComment],
    y_positions: list[int], x_start: float, margin_w: float, page_h: float,
) -> None:
    BOX_W = margin_w - 10
    BOX_PAD = 5
    FONT_SZ = 7
    LINE_H = 10
    MIN_GAP = 6
    COLOURS = {
        "positive": (_GREEN, (0.90, 0.98, 0.93)),
        "neutral":  (_BLUE,  (0.92, 0.93, 0.99)),
        "negative": (_RED,   (0.99, 0.92, 0.92)),
    }
    ICONS = {"positive": "✓", "neutral": "•", "negative": "✗"}
    next_y_pdf = page_h - 28

    sorted_c = sorted(
        comments,
        key=lambda c: -(y_positions[c.paragraph_index]
                        if c.paragraph_index < len(y_positions) else 0),
    )
    for comment in sorted_c:
        stroke, fill = COLOURS.get(comment.sentiment, COLOURS["neutral"])
        icon = ICONS.get(comment.sentiment, "•")
        words = comment.comment_text.split()
        lines: list[str] = []
        current = ""
        for word in words:
            test = f"{current} {word}".strip()
            if len(test) * 4.5 <= BOX_W - 20:
                current = test
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        lines = lines or [""]
        box_h = BOX_PAD * 2 + LINE_H * len(lines)
        y_box = next_y_pdf - box_h
        if y_box < 10:
            break
        canvas.setFillColorRGB(*fill)
        canvas.rect(x_start + 5, y_box, BOX_W, box_h, fill=1, stroke=0)
        canvas.setFillColorRGB(*stroke)
        canvas.rect(x_start + 5, y_box, 3, box_h, fill=1, stroke=0)
        canvas.setFillColorRGB(*stroke)
        canvas.setFont("Helvetica-Bold", FONT_SZ + 1)
        canvas.drawString(x_start + 11, y_box + BOX_PAD + (len(lines) - 1) * LINE_H, icon)
        canvas.setFillColorRGB(*_DARK)
        canvas.setFont("Helvetica", FONT_SZ)
        for i, line in enumerate(lines):
            canvas.drawString(x_start + 22, y_box + BOX_PAD + (len(lines) - 1 - i) * LINE_H, line)
        next_y_pdf = y_box - MIN_GAP


def _draw_page_footer(canvas: Canvas, page_num: int, total: int, W: float) -> None:
    canvas.setFont("Helvetica", 7)
    canvas.setFillColorRGB(*_LIGHT)
    canvas.drawString(8 * mm, 8 * mm, f"Page {page_num + 1} of {total + 1}")
    canvas.drawRightString(W - 8 * mm, 8 * mm, "EvalPro — Checked Answer")


# ── Essay summary page (Roundtable IAS style) ─────────────────────────────────

def _render_essay_summary_page(
    canvas: Canvas, evaluation: EvaluationResult,
    question: str | None, exam_type: str, job_id: str,
    W: float, H: float,
) -> None:
    """Render the essay evaluation sheet matching the Roundtable IAS sample."""
    from datetime import datetime, timezone
    now = datetime.now(tz=timezone.utc).strftime("%d %b %Y")
    MARGIN = 18 * mm
    total  = evaluation.total_score
    max_t  = evaluation.max_total_score

    pct = total / max_t if max_t else 0
    grade_rgb = (
        _GREEN if pct >= 0.8 else
        _VIOLET if pct >= 0.6 else
        _AMBER if pct >= 0.4 else
        _RED
    )

    # ── Header bar ────────────────────────────────────────────────────────────
    canvas.setFillColorRGB(*_VIOLET)
    canvas.rect(0, H - 20 * mm, W, 20 * mm, fill=1, stroke=0)
    canvas.setFillColorRGB(1, 1, 1)
    canvas.setFont("Helvetica-Bold", 10)
    canvas.drawString(MARGIN, H - 9 * mm, "ROUNDTABLE IAS  ·  ESSAY MENTORSHIP CELL")
    canvas.setFont("Helvetica-Bold", 14)
    canvas.drawString(MARGIN, H - 16 * mm, "Essay Evaluation Sheet")

    # Right-side meta
    canvas.setFont("Helvetica", 7)
    canvas.drawRightString(W - MARGIN, H - 8 * mm,  f"Paper: Essay  ·  Word limit: 1200")
    canvas.drawRightString(W - MARGIN, H - 12 * mm, f"Length: ~{evaluation.annotation_comments and 'see text' or 'N/A'}")
    canvas.drawRightString(W - MARGIN, H - 16 * mm, f"Evaluated: {now}")

    y = H - 26 * mm

    # ── Topic block ───────────────────────────────────────────────────────────
    canvas.setFillColorRGB(0.94, 0.94, 0.98)
    canvas.rect(MARGIN, y - 10 * mm, W - 2 * MARGIN, 10 * mm, fill=1, stroke=0)
    canvas.setStrokeColorRGB(*_VIOLET)
    canvas.setLineWidth(0.5)
    canvas.rect(MARGIN, y - 10 * mm, W - 2 * MARGIN, 10 * mm, fill=0, stroke=1)
    canvas.setFillColorRGB(*_DARK)
    canvas.setFont("Helvetica-Bold", 7)
    canvas.drawString(MARGIN + 3 * mm, y - 3 * mm, "TOPIC")
    canvas.setFont("Helvetica", 8)
    topic = (question or exam_type)[:120]
    canvas.drawString(MARGIN + 3 * mm, y - 8 * mm, f'"{topic}"')
    y -= 14 * mm

    # ── Parameter table ───────────────────────────────────────────────────────
    COL_PARAM  = (W - 2 * MARGIN) * 0.42
    COL_MAX    = (W - 2 * MARGIN) * 0.08
    COL_MARKS  = (W - 2 * MARGIN) * 0.10
    COL_REMARK = (W - 2 * MARGIN) * 0.40
    ROW_H = 8 * mm

    # Table header
    canvas.setFillColorRGB(*_DARK)
    canvas.rect(MARGIN, y - ROW_H, W - 2 * MARGIN, ROW_H, fill=1, stroke=0)
    canvas.setFillColorRGB(1, 1, 1)
    canvas.setFont("Helvetica-Bold", 7)
    hx = MARGIN + 2 * mm
    canvas.drawString(hx,                           y - 5.5 * mm, "PARAMETER")
    canvas.drawString(hx + COL_PARAM,               y - 5.5 * mm, "MAX")
    canvas.drawString(hx + COL_PARAM + COL_MAX,     y - 5.5 * mm, "MARKS")
    canvas.drawString(hx + COL_PARAM + COL_MAX + COL_MARKS, y - 5.5 * mm, "EXAMINER'S REMARK")
    y -= ROW_H

    for i, eps in enumerate(evaluation.essay_parameter_scores):
        row_fill = (1.0, 1.0, 1.0) if i % 2 == 0 else (0.97, 0.97, 0.99)
        canvas.setFillColorRGB(*row_fill)
        canvas.rect(MARGIN, y - ROW_H, W - 2 * MARGIN, ROW_H, fill=1, stroke=0)

        # Score colour
        pct_p = eps.score / eps.max_score if eps.max_score else 0
        s_rgb = _GREEN if pct_p >= 0.75 else (_AMBER if pct_p >= 0.5 else _RED)

        canvas.setFillColorRGB(*_DARK)
        canvas.setFont("Helvetica", 7)
        rx = MARGIN + 2 * mm
        # Truncate parameter name to fit
        pname = eps.parameter[:36]
        canvas.drawString(rx, y - 5.5 * mm, pname)
        canvas.drawString(rx + COL_PARAM, y - 5.5 * mm, str(eps.max_score))

        canvas.setFillColorRGB(*s_rgb)
        canvas.setFont("Helvetica-Bold", 8)
        canvas.drawString(rx + COL_PARAM + COL_MAX, y - 5.5 * mm, str(eps.score))

        canvas.setFillColorRGB(*_DARK)
        canvas.setFont("Helvetica", 6.5)
        remark = eps.examiner_remark[:72]
        canvas.drawString(rx + COL_PARAM + COL_MAX + COL_MARKS, y - 5.5 * mm, remark)

        # Row border
        canvas.setStrokeColorRGB(*_LIGHT)
        canvas.setLineWidth(0.3)
        canvas.line(MARGIN, y - ROW_H, W - MARGIN, y - ROW_H)
        y -= ROW_H

    # Total score row
    canvas.setFillColorRGB(*_DARK)
    canvas.rect(MARGIN, y - ROW_H, W - 2 * MARGIN, ROW_H, fill=1, stroke=0)
    canvas.setFillColorRGB(1, 1, 1)
    canvas.setFont("Helvetica-Bold", 9)
    canvas.drawString(MARGIN + 2 * mm, y - 6 * mm, "TOTAL SCORE")
    canvas.setFillColorRGB(*grade_rgb)
    canvas.setFont("Helvetica-Bold", 13)
    canvas.drawRightString(W - MARGIN - 2 * mm, y - 6 * mm, f"{total} / {max_t}")
    y -= ROW_H + 6 * mm

    # ── Overall remarks block ─────────────────────────────────────────────────
    if y > 40 * mm:
        canvas.setFillColorRGB(*_VIOLET)
        canvas.setFont("Helvetica-Bold", 8)
        canvas.drawString(MARGIN, y, "OVERALL REMARKS")
        y -= 4 * mm

        canvas.setFillColorRGB(0.97, 0.95, 1.0)
        remark_h = min(20 * mm, max(10 * mm, len(evaluation.overall_remark) * 0.35))
        canvas.rect(MARGIN, y - remark_h, W - 2 * MARGIN, remark_h, fill=1, stroke=0)
        canvas.setStrokeColorRGB(*_VIOLET)
        canvas.setLineWidth(0.4)
        canvas.rect(MARGIN, y - remark_h, W - 2 * MARGIN, remark_h, fill=0, stroke=1)
        canvas.setFillColorRGB(*_DARK)
        canvas.setFont("Helvetica-Oblique", 7.5)
        _draw_wrapped_text(canvas, evaluation.overall_remark,
                           MARGIN + 3 * mm, y - 4 * mm, W - 2 * MARGIN - 6 * mm, 7.5)
        y -= remark_h + 5 * mm

    # ── Before You Resubmit ───────────────────────────────────────────────────
    if evaluation.before_resubmit and y > 30 * mm:
        # Dashed separator
        canvas.setDash(3, 3)
        canvas.setStrokeColorRGB(*_LIGHT)
        canvas.setLineWidth(0.5)
        canvas.line(MARGIN, y, W - MARGIN, y)
        canvas.setDash()
        y -= 5 * mm

        canvas.setFillColorRGB(*_DARK)
        canvas.setFont("Helvetica-Bold", 8)
        canvas.drawString(MARGIN, y, "BEFORE YOU RESUBMIT")
        y -= 5 * mm

        # Two-column layout for the checklist items
        items = evaluation.before_resubmit
        mid   = (len(items) + 1) // 2
        left  = items[:mid]
        right = items[mid:]
        col_w = (W - 2 * MARGIN - 6 * mm) / 2

        canvas.setFont("Helvetica", 7)
        canvas.setFillColorRGB(*_DARK)
        row_y = y
        for i, item in enumerate(left):
            num = i + 1
            canvas.setFillColorRGB(*_VIOLET)
            canvas.circle(MARGIN + 3.5 * mm, row_y - 1.5 * mm, 3.5 * mm, fill=1, stroke=0)
            canvas.setFillColorRGB(1, 1, 1)
            canvas.setFont("Helvetica-Bold", 6)
            canvas.drawCentredString(MARGIN + 3.5 * mm, row_y - 3 * mm, str(num))
            canvas.setFillColorRGB(*_DARK)
            canvas.setFont("Helvetica", 7)
            _draw_wrapped_text(canvas, item, MARGIN + 8 * mm, row_y - 1 * mm, col_w - 8 * mm, 7)
            row_y -= 10 * mm

        row_y = y
        rx_start = MARGIN + col_w + 6 * mm
        for j, item in enumerate(right):
            num = mid + j + 1
            canvas.setFillColorRGB(*_VIOLET)
            canvas.circle(rx_start + 3.5 * mm, row_y - 1.5 * mm, 3.5 * mm, fill=1, stroke=0)
            canvas.setFillColorRGB(1, 1, 1)
            canvas.setFont("Helvetica-Bold", 6)
            canvas.drawCentredString(rx_start + 3.5 * mm, row_y - 3 * mm, str(num))
            canvas.setFillColorRGB(*_DARK)
            canvas.setFont("Helvetica", 7)
            _draw_wrapped_text(canvas, item, rx_start + 8 * mm, row_y - 1 * mm, col_w - 8 * mm, 7)
            row_y -= 10 * mm

    # ── Footer ────────────────────────────────────────────────────────────────
    canvas.setFont("Helvetica", 7)
    canvas.setFillColorRGB(*_LIGHT)
    canvas.drawString(MARGIN, 8 * mm, "theroundtableias.com")
    canvas.drawRightString(W - MARGIN, 8 * mm, "RoundtableIAS  ·  YouTube")


# ── Standard summary page (original 5-param layout) ──────────────────────────

def _render_standard_summary_page(
    canvas: Canvas, evaluation: EvaluationResult,
    question: str | None, exam_type: str, job_id: str,
    W: float, H: float,
) -> None:
    """Render the final summary score sheet page for non-essay exams."""
    from datetime import datetime, timezone
    now = datetime.now(tz=timezone.utc).strftime("%d %b %Y  %H:%M UTC")
    MARGIN = 20 * mm

    pct = evaluation.total_score / evaluation.max_total_score if evaluation.max_total_score else 0
    grade = "A" if pct >= 0.8 else "B" if pct >= 0.6 else "C" if pct >= 0.4 else "D"
    grade_rgb = (
        _GREEN if pct >= 0.8 else _VIOLET if pct >= 0.6 else _AMBER if pct >= 0.4 else _RED
    )

    # Header bar
    canvas.setFillColorRGB(*_VIOLET)
    canvas.rect(0, H - 14 * mm, W, 14 * mm, fill=1, stroke=0)
    canvas.setFillColorRGB(1, 1, 1)
    canvas.setFont("Helvetica-Bold", 13)
    canvas.drawString(MARGIN, H - 10 * mm, "Evaluation Summary — Final Score Sheet")

    y = H - 28 * mm
    canvas.setFillColorRGB(*_DARK)
    canvas.setFont("Helvetica-Bold", 9)
    canvas.drawString(MARGIN, y, f"Exam Type: {exam_type}")
    y -= 5 * mm
    if question:
        canvas.setFont("Helvetica", 8)
        _draw_wrapped_text(canvas, f"Question: {question}", MARGIN, y, W - 2 * MARGIN, 8)
        y -= 8 * mm
    canvas.setFont("Helvetica", 7)
    canvas.setFillColorRGB(*_LIGHT)
    canvas.drawString(MARGIN, y, f"Generated: {now}   |   Job ID: {job_id}")
    y -= 6 * mm

    # Score hero
    canvas.setFillColorRGB(0.97, 0.97, 0.99)
    canvas.roundRect(MARGIN, y - 28 * mm, W - 2 * MARGIN, 28 * mm, 6, fill=1, stroke=0)
    canvas.setFillColorRGB(*grade_rgb)
    canvas.setFont("Helvetica-Bold", 42)
    canvas.drawString(MARGIN + 6 * mm, y - 20 * mm, str(evaluation.total_score))
    canvas.setFont("Helvetica", 18)
    canvas.setFillColorRGB(*_LIGHT)
    canvas.drawString(MARGIN + 26 * mm, y - 20 * mm, f"/ {evaluation.max_total_score}")
    canvas.setFillColorRGB(*grade_rgb)
    canvas.setFont("Helvetica-Bold", 48)
    canvas.drawString(W - MARGIN - 22 * mm, y - 22 * mm, grade)
    y -= 34 * mm

    y = _draw_standard_param_table(canvas, evaluation, MARGIN, y, W)
    y -= 5 * mm

    if evaluation.strengths:
        canvas.setFillColorRGB(*_GREEN)
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawString(MARGIN, y, "Strengths")
        y -= 4 * mm
        canvas.setFont("Helvetica", 8)
        canvas.setFillColorRGB(*_DARK)
        for s in evaluation.strengths:
            canvas.drawString(MARGIN + 4 * mm, y, f"✓  {s}")
            y -= 4 * mm
        y -= 2 * mm

    if evaluation.improvements:
        canvas.setFillColorRGB(*_RED)
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawString(MARGIN, y, "Areas for Improvement")
        y -= 4 * mm
        canvas.setFont("Helvetica", 8)
        canvas.setFillColorRGB(*_DARK)
        for imp in evaluation.improvements:
            canvas.drawString(MARGIN + 4 * mm, y, f"✗  {imp}")
            y -= 4 * mm

    if y > 20 * mm:
        canvas.setFillColorRGB(*_VIOLET)
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawString(MARGIN, y, "Examiner's Remark")
        y -= 4 * mm
        canvas.setFillColorRGB(0.97, 0.95, 1.0)
        canvas.roundRect(MARGIN, y - 12 * mm, W - 2 * MARGIN, 12 * mm, 4, fill=1, stroke=0)
        canvas.setFillColorRGB(*_DARK)
        canvas.setFont("Helvetica-Oblique", 8)
        _draw_wrapped_text(canvas, f'"{evaluation.overall_remark}"',
                           MARGIN + 4 * mm, y - 4 * mm, W - 2 * MARGIN - 8 * mm, 8)

    canvas.setFont("Helvetica", 7)
    canvas.setFillColorRGB(*_LIGHT)
    canvas.drawString(MARGIN, 8 * mm, "EvalPro — Final Report")
    canvas.drawRightString(W - MARGIN, 8 * mm, f"Page {len(evaluation.annotation_comments) + 1}")


def _draw_standard_param_table(
    canvas: Canvas, evaluation: EvaluationResult,
    x: float, y: float, W: float,
) -> float:
    """Draw the 5-parameter score table. Returns updated Y."""
    MARGIN = 20 * mm
    col_w  = (W - 2 * MARGIN) / 3
    ROW_H  = 12 * mm

    headers = ["Parameter", "Score", "Feedback"]
    canvas.setFillColorRGB(*_DARK)
    canvas.rect(MARGIN, y - ROW_H, W - 2 * MARGIN, ROW_H, fill=1, stroke=0)
    canvas.setFillColorRGB(1, 1, 1)
    canvas.setFont("Helvetica-Bold", 8)
    for i, h in enumerate(headers):
        canvas.drawString(MARGIN + i * col_w + 4, y - 8, h)
    y -= ROW_H

    for i, ps in enumerate(evaluation.parameter_scores):
        row_fill = (1, 1, 1) if i % 2 == 0 else (0.97, 0.97, 0.99)
        canvas.setFillColorRGB(*row_fill)
        canvas.rect(MARGIN, y - ROW_H, W - 2 * MARGIN, ROW_H, fill=1, stroke=0)
        pct_p = ps.score / ps.max_score if ps.max_score else 0
        s_rgb = _GREEN if pct_p >= 0.75 else (_AMBER if pct_p >= 0.5 else _RED)
        canvas.setFillColorRGB(*_DARK)
        canvas.setFont("Helvetica", 7)
        canvas.drawString(MARGIN + 4, y - 8, str(ps.parameter))
        canvas.setFillColorRGB(*s_rgb)
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawString(MARGIN + col_w + 4, y - 8, f"{ps.score}/{ps.max_score}")
        canvas.setFillColorRGB(*_DARK)
        canvas.setFont("Helvetica", 6.5)
        canvas.drawString(MARGIN + col_w * 2 + 4, y - 8, ps.justification[:55])
        canvas.setStrokeColorRGB(*_LIGHT)
        canvas.setLineWidth(0.3)
        canvas.line(MARGIN, y - ROW_H, W - MARGIN, y - ROW_H)
        y -= ROW_H

    return y


# ── Shared helpers ────────────────────────────────────────────────────────────

def _distribute_comments(
    comments: list[AnnotationComment], num_pages: int
) -> list[list[AnnotationComment]]:
    """Distribute annotation comments evenly across pages."""
    if num_pages <= 0:
        return []
    if num_pages == 1:
        return [comments]
    per_page: list[list[AnnotationComment]] = [[] for _ in range(num_pages)]
    for i, comment in enumerate(comments):
        per_page[i % num_pages].append(comment)
    return per_page


def _pil_to_reportlab(image: Image.Image):
    """Convert a PIL Image to a reportlab ImageReader."""
    from reportlab.lib.utils import ImageReader
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=88)
    buf.seek(0)
    return ImageReader(buf)


def _draw_wrapped_text(
    canvas: Canvas, text: str,
    x: float, y: float, max_w: float, font_size: float,
) -> None:
    """Draw word-wrapped text using reportlab canvas (no Platypus)."""
    words   = text.split()
    lines   : list[str] = []
    current = ""
    char_w  = font_size * 0.52   # rough average char width

    for word in words:
        test = f"{current} {word}".strip()
        if len(test) * char_w <= max_w:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)

    line_h = font_size * 1.35
    for i, line in enumerate(lines):
        canvas.drawString(x, y - i * line_h, line)
