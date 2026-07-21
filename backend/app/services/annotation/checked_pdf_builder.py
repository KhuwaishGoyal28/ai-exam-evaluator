"""
Builds a "checked PDF" — the original answer with ink marks and margin notes
embedded on each page, exactly like a human teacher's marked paper.

Single responsibility: original pages + evaluation → checked PDF bytes.

Layout per page:
  - Original answer page (as background)
  - Red ink marks overlaid (tick, cross, wavy underlines)
  - Right margin panel with comment boxes (coloured by sentiment)
  - Page-level score annotation in the bottom-right corner

Final page: summary score sheet (no answer content).
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

# Margin panel width (proportion of page width)
_MARGIN_RATIO = 0.30
_RED          = (0.86, 0.15, 0.15)
_GREEN        = (0.09, 0.64, 0.29)
_BLUE         = (0.15, 0.39, 0.92)
_DARK         = (0.06, 0.09, 0.16)
_LIGHT        = (0.58, 0.64, 0.72)
_VIOLET       = (0.49, 0.23, 0.93)


def build_checked_pdf(
    page_images: list[Image.Image],
    evaluation: EvaluationResult,
    question: str | None,
    exam_type: str,
    job_id: str,
) -> bytes:
    """
    Build a complete checked PDF from a list of answer page images.
    Returns raw PDF bytes.
    """
    buf = io.BytesIO()
    comments = evaluation.annotation_comments

    # Distribute comments across pages (round-robin if single page)
    pages_comments = _distribute_comments(comments, len(page_images))

    c = Canvas(buf, pagesize=A4)
    W, H = A4

    for page_num, (page_img, page_comments) in enumerate(
        zip(page_images, pages_comments)
    ):
        _render_checked_page(
            canvas=c,
            page_img=page_img,
            page_comments=page_comments,
            page_num=page_num,
            total_pages=len(page_images),
            evaluation=evaluation,
            W=W, H=H,
        )
        c.showPage()

    # Final summary page
    _render_summary_page(c, evaluation, question, exam_type, job_id, W, H)
    c.showPage()

    c.save()
    pdf_bytes = buf.getvalue()
    logger.info("checked_pdf_built", pages=len(page_images) + 1, size_bytes=len(pdf_bytes))
    return pdf_bytes


def _render_checked_page(
    canvas: Canvas,
    page_img: Image.Image,
    page_comments: list[AnnotationComment],
    page_num: int,
    total_pages: int,
    evaluation: EvaluationResult,
    W: float, H: float,
) -> None:
    """Render one answer page with ink marks and margin notes."""
    margin_w = W * _MARGIN_RATIO
    answer_w = W - margin_w

    # ── Draw ink marks on the page image ──────────────────────────────────
    y_positions = compute_paragraph_y_positions(
        image_height=page_img.height,
        num_paragraphs=max(len(page_comments), 1),
    )
    marked_img = draw_ink_marks(page_img, page_comments, y_positions, page_img.width)

    # ── Paste the marked image into the answer area ────────────────────────
    img_buf = io.BytesIO()
    marked_img.save(img_buf, format="JPEG", quality=88)
    img_buf.seek(0)

    # Scale to fit answer_w × H
    canvas.drawImage(
        _pil_to_reportlab(marked_img),
        0, 0,
        width=answer_w,
        height=H,
        preserveAspectRatio=True,
        anchor="nw",
    )

    # ── Margin panel background ────────────────────────────────────────────
    canvas.setFillColorRGB(0.97, 0.97, 0.99)
    canvas.rect(answer_w, 0, margin_w, H, fill=1, stroke=0)

    # Separator line
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

    # ── Draw margin comment boxes ──────────────────────────────────────────
    _draw_margin_comments(canvas, page_comments, y_positions, answer_w, margin_w, H)

    # ── Page footer ───────────────────────────────────────────────────────
    _draw_page_footer(canvas, page_num, total_pages, W)


def _draw_margin_comments(
    canvas: Canvas,
    comments: list[AnnotationComment],
    y_positions: list[int],
    x_start: float,
    margin_w: float,
    page_h: float,
) -> None:
    """Draw stacked comment boxes in the right margin."""
    BOX_W   = margin_w - 10
    BOX_PAD = 5
    FONT_SZ = 7
    LINE_H  = 10
    MIN_GAP = 6

    COLOURS = {
        "positive": (_GREEN, (0.90, 0.98, 0.93)),
        "neutral":  (_BLUE,  (0.92, 0.93, 0.99)),
        "negative": (_RED,   (0.99, 0.92, 0.92)),
    }
    ICONS = {"positive": "✓", "neutral": "•", "negative": "✗"}

    next_y_pdf = page_h - 28   # start just below the header (PDF coords: y=0 is bottom)

    sorted_c = sorted(
        comments,
        key=lambda c: -(y_positions[c.paragraph_index]
                        if c.paragraph_index < len(y_positions) else 0),
    )

    for comment in sorted_c:
        stroke, fill = COLOURS.get(comment.sentiment, COLOURS["neutral"])
        icon         = ICONS.get(comment.sentiment, "•")

        # Word-wrap the comment text
        words   = comment.comment_text.split()
        lines   : list[str] = []
        current = ""
        for word in words:
            test = f"{current} {word}".strip()
            if len(test) * 4.5 <= BOX_W - 20:  # rough char width estimation
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
            break   # no more space on this page

        # Box background
        canvas.setFillColorRGB(*fill)
        canvas.rect(x_start + 5, y_box, BOX_W, box_h, fill=1, stroke=0)

        # Left accent bar
        canvas.setFillColorRGB(*stroke)
        canvas.rect(x_start + 5, y_box, 3, box_h, fill=1, stroke=0)

        # Icon
        canvas.setFillColorRGB(*stroke)
        canvas.setFont("Helvetica-Bold", FONT_SZ + 1)
        canvas.drawString(x_start + 11, y_box + BOX_PAD + (len(lines) - 1) * LINE_H, icon)

        # Text lines
        canvas.setFillColorRGB(*_DARK)
        canvas.setFont("Helvetica", FONT_SZ)
        for i, line in enumerate(lines):
            canvas.drawString(
                x_start + 22,
                y_box + BOX_PAD + (len(lines) - 1 - i) * LINE_H,
                line,
            )

        next_y_pdf = y_box - MIN_GAP


def _draw_page_footer(canvas: Canvas, page_num: int, total: int, W: float) -> None:
    """Draw a subtle page footer."""
    canvas.setFont("Helvetica", 7)
    canvas.setFillColorRGB(*_LIGHT)
    canvas.drawString(8 * mm, 8 * mm, f"Page {page_num + 1} of {total + 1}")
    canvas.drawRightString(W - 8 * mm, 8 * mm, "EvalPro — Checked Answer")


def _render_summary_page(
    canvas: Canvas,
    evaluation: EvaluationResult,
    question: str | None,
    exam_type: str,
    job_id: str,
    W: float, H: float,
) -> None:
    """Render the final summary score sheet page."""
    from datetime import datetime, timezone
    now = datetime.now(tz=timezone.utc).strftime("%d %b %Y  %H:%M UTC")

    pct   = evaluation.total_score / evaluation.max_total_score if evaluation.max_total_score else 0
    grade = "A" if pct >= 0.8 else "B" if pct >= 0.6 else "C" if pct >= 0.4 else "D"
    grade_rgb = (
        (0.09, 0.64, 0.29) if pct >= 0.8 else
        (0.49, 0.23, 0.93) if pct >= 0.6 else
        (0.85, 0.53, 0.04) if pct >= 0.4 else
        (0.86, 0.15, 0.15)
    )

    MARGIN = 20 * mm

    # ── Header bar ────────────────────────────────────────────────────────
    canvas.setFillColorRGB(0.49, 0.23, 0.93)
    canvas.rect(0, H - 14 * mm, W, 14 * mm, fill=1, stroke=0)
    canvas.setFillColorRGB(1, 1, 1)
    canvas.setFont("Helvetica-Bold", 13)
    canvas.drawString(MARGIN, H - 10 * mm, "Evaluation Summary — Final Score Sheet")

    y = H - 28 * mm

    # ── Exam / question metadata ───────────────────────────────────────────
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

    # ── Score hero ────────────────────────────────────────────────────────
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

    # ── Parameter table ───────────────────────────────────────────────────
    y = _draw_parameter_table(canvas, evaluation, MARGIN, y, W)
    y -= 5 * mm

    # ── Strengths ─────────────────────────────────────────────────────────
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

    # ── Improvements ──────────────────────────────────────────────────────
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
        y -= 2 * mm

    # ── Overall remark ────────────────────────────────────────────────────
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

    # Footer
    canvas.setFont("Helvetica", 7)
    canvas.setFillColorRGB(*_LIGHT)
    canvas.drawString(MARGIN, 8 * mm, "EvalPro — Final Report")
    canvas.drawRightString(W - MARGIN, 8 * mm, f"Page {len(evaluation.annotation_comments) + 1} of {len(evaluation.annotation_comments) + 1}")


def _draw_parameter_table(
    canvas: Canvas,
    evaluation: EvaluationResult,
    x: float, y: float, W: float,
) -> float:
    """Draw the 5-parameter score table. Returns updated Y."""
    MARGIN = 20 * mm
    col_w  = (W - 2 * MARGIN) / 3
    ROW_H  = 12 * mm

    PARAM_ICONS = {
        "Structure": "STRUCT",
        "Content & Accuracy": "CONTENT",
        "Language & Expression": "LANG",
        "Relevance to Question": "RELEVANCE",
        "Critical Thinking": "CRITICAL",
    }

    canvas.setFillColorRGB(0.49, 0.23, 0.93)
    canvas.setFont("Helvetica-Bold", 8)
    canvas.rect(x, y - ROW_H, W - 2 * MARGIN, ROW_H, fill=1, stroke=0)
    canvas.setFillColorRGB(1, 1, 1)
    canvas.drawString(x + 4, y - ROW_H + 4, "Parameter")
    canvas.drawString(x + col_w + 4, y - ROW_H + 4, "Score")
    canvas.drawString(x + col_w * 1.5 + 4, y - ROW_H + 4, "Feedback")
    y -= ROW_H

    for i, ps in enumerate(evaluation.parameter_scores):
        pct     = ps.score / ps.max_score if ps.max_score else 0
        bar_rgb = (
            (0.09, 0.64, 0.29) if pct >= 0.75 else
            (0.85, 0.53, 0.04) if pct >= 0.5 else
            (0.86, 0.15, 0.15)
        )
        bg = (1, 1, 1) if i % 2 == 0 else (0.97, 0.97, 0.99)
        canvas.setFillColorRGB(*bg)
        canvas.rect(x, y - ROW_H, W - 2 * MARGIN, ROW_H, fill=1, stroke=0)

        # Parameter name
        canvas.setFillColorRGB(*_DARK)
        canvas.setFont("Helvetica-Bold", 7)
        canvas.drawString(x + 4, y - ROW_H + 5, ps.parameter)

        # Score bar
        bar_max  = col_w * 0.8
        bar_fill = bar_max * pct
        canvas.setFillColorRGB(0.89, 0.89, 0.89)
        canvas.rect(x + col_w + 4, y - ROW_H + 6, bar_max, 5, fill=1, stroke=0)
        canvas.setFillColorRGB(*bar_rgb)
        canvas.rect(x + col_w + 4, y - ROW_H + 6, bar_fill, 5, fill=1, stroke=0)
        canvas.setFont("Helvetica-Bold", 8)
        canvas.setFillColorRGB(*bar_rgb)
        canvas.drawString(x + col_w + 4 + bar_max + 3, y - ROW_H + 4, f"{ps.score}/{ps.max_score}")

        # Justification (truncated)
        canvas.setFillColorRGB(*_DARK)
        canvas.setFont("Helvetica", 6)
        just = ps.justification[:80] + ("…" if len(ps.justification) > 80 else "")
        canvas.drawString(x + col_w * 1.5 + 4, y - ROW_H + 5, just)

        y -= ROW_H

    return y


def _draw_wrapped_text(
    canvas: Canvas, text: str, x: float, y: float, max_w: float, font_size: int
) -> None:
    """Simple word-wrap for canvas text (no return value — cosmetic only)."""
    words   = text.split()
    current = ""
    char_w  = font_size * 0.55

    for word in words:
        test = f"{current} {word}".strip()
        if len(test) * char_w <= max_w:
            current = test
        else:
            if current:
                canvas.drawString(x, y, current)
                y -= font_size * 1.5
            current = word
    if current:
        canvas.drawString(x, y, current)


def _pil_to_reportlab(image: Image.Image):
    """Convert a PIL image to a reportlab ImageReader."""
    from reportlab.lib.utils import ImageReader
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=85)
    buf.seek(0)
    return ImageReader(buf)


def _distribute_comments(
    comments: list[AnnotationComment], num_pages: int
) -> list[list[AnnotationComment]]:
    """
    Distribute annotation comments across pages.
    If there's only 1 page, all comments go on page 0.
    """
    if num_pages <= 1:
        return [comments]

    result: list[list[AnnotationComment]] = [[] for _ in range(num_pages)]
    for c in comments:
        page_idx = min(c.paragraph_index, num_pages - 1)
        result[page_idx].append(c)
    return result
