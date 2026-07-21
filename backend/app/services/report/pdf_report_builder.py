"""
Generates a formatted PDF evaluation report using reportlab.
Single responsibility: EvaluateResponse + metadata → PDF bytes.

Layout:
  Page 1 — Header, Job info, Overall score ring (text-based), Overall remark
  Page 2 — Parameter scores (progress bars), Strengths, Improvements
  Page 3 — Extracted text, Annotation comments
  (Any page) — Footer with job ID and timestamp
"""
from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

if TYPE_CHECKING:
    from app.models.responses.evaluate import EvaluateResponse

from app.core.logging import get_logger

logger = get_logger(__name__)

# ── Colour palette (violet/teal theme) ───────────────────────────────────────
_C_PRIMARY    = colors.HexColor("#7c3aed")   # violet-700
_C_TEAL       = colors.HexColor("#0d9488")   # teal-600
_C_DARK       = colors.HexColor("#0f172a")   # slate-900
_C_MID        = colors.HexColor("#475569")   # slate-600
_C_LIGHT      = colors.HexColor("#94a3b8")   # slate-400
_C_BG         = colors.HexColor("#f8fafc")   # slate-50
_C_WHITE      = colors.white
_C_SUCCESS    = colors.HexColor("#059669")   # emerald-600
_C_WARNING    = colors.HexColor("#d97706")   # amber-600
_C_DANGER     = colors.HexColor("#dc2626")   # red-600
_C_BORDER     = colors.HexColor("#e2e8f0")   # slate-200

W, H = A4  # 595 × 842 pts
MARGIN = 20 * mm


def build_pdf_report(
    response: "EvaluateResponse",
    question: str | None,
    exam_type: str,
) -> bytes:
    """
    Build a complete evaluation report PDF and return raw bytes.
    This is the only public function in this module.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN + 8 * mm,
        title="Evaluation Report",
        author="EvalPro",
    )

    styles = _build_styles()
    story  = _build_story(response, question, exam_type, styles)

    doc.build(
        story,
        onFirstPage=_draw_footer,
        onLaterPages=_draw_footer,
    )

    pdf_bytes = buf.getvalue()
    logger.info("pdf_report_built", size_bytes=len(pdf_bytes))
    return pdf_bytes


# ── Story builder ─────────────────────────────────────────────────────────────

def _build_story(response, question, exam_type, styles) -> list:
    ev    = response.evaluation
    story = []

    # ── Page 1: cover + overall score ──────────────────────────────────────
    story += _build_header_section(response.job_id, exam_type, question, styles)
    story += _build_score_hero(ev, styles)
    story += _build_overall_remark(ev.overall_remark, styles)
    story.append(PageBreak())

    # ── Page 2: parameter breakdown + strengths/improvements ───────────────
    story += _build_parameter_table(ev.parameter_scores, styles)
    if ev.strengths:
        story += _build_bullet_section("Strengths", ev.strengths, _C_SUCCESS, styles)
    if ev.improvements:
        story += _build_bullet_section("Areas for Improvement", ev.improvements, _C_DANGER, styles)
    story.append(PageBreak())

    # ── Page 3: extracted text + annotations ───────────────────────────────
    story += _build_extracted_text(response.extracted_text, response.word_count, styles)
    if response.annotation_comments:
        story += _build_annotation_section(response.annotation_comments, styles)

    return story


# ── Section builders (each builds one logical section) ───────────────────────

def _build_header_section(job_id, exam_type, question, styles) -> list:
    """Title banner + job metadata."""
    now = datetime.now(tz=timezone.utc).strftime("%d %b %Y  %H:%M UTC")

    items = [
        # Gradient-style top bar (simulated with coloured rectangle)
        Table(
            [[""]],
            colWidths=[W - 2 * MARGIN],
            rowHeights=[6],
            style=TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), _C_PRIMARY),
                ("LINEBELOW",  (0, 0), (-1, -1), 0, _C_PRIMARY),
            ]),
        ),
        Spacer(1, 6 * mm),
        Paragraph("Evaluation Report", styles["title"]),
        Spacer(1, 2 * mm),
        Paragraph(f"Exam Type: <b>{exam_type}</b>", styles["meta"]),
    ]

    if question:
        items.append(Paragraph(f"Question: {question}", styles["meta"]))

    items += [
        Paragraph(f"Generated: {now}", styles["meta"]),
        Paragraph(f"Job ID: <font face='Courier' size='7'>{job_id}</font>", styles["meta"]),
        Spacer(1, 6 * mm),
        HRFlowable(width="100%", thickness=1, color=_C_BORDER),
        Spacer(1, 4 * mm),
    ]
    return items


def _build_score_hero(ev, styles) -> list:
    """Big score number + grade badge centred on the page."""
    pct   = ev.total_score / ev.max_total_score if ev.max_total_score else 0
    grade = _letter_grade(pct)
    grade_colour = (
        _C_SUCCESS if pct >= 0.8 else
        _C_PRIMARY if pct >= 0.6 else
        _C_WARNING if pct >= 0.4 else
        _C_DANGER
    )
    grade_label = (
        "Outstanding" if pct >= 0.8 else
        "Good"        if pct >= 0.6 else
        "Average"     if pct >= 0.4 else
        "Needs Work"
    )

    data = [[
        Paragraph(
            f'<font size="48" color="{grade_colour.hexval()}">'
            f'<b>{ev.total_score}</b></font>'
            f'<font size="20" color="#94a3b8"> / {ev.max_total_score}</font>',
            styles["center"],
        ),
        Paragraph(
            f'<font size="36" color="{grade_colour.hexval()}"><b>{grade}</b></font><br/>'
            f'<font size="10" color="#64748b">{grade_label}</font>',
            styles["center"],
        ),
    ]]

    tbl = Table(data, colWidths=[(W - 2 * MARGIN) * 0.55, (W - 2 * MARGIN) * 0.45])
    tbl.setStyle(TableStyle([
        ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND", (0, 0), (-1, -1), _C_BG),
        ("ROUNDEDCORNERS", [6]),
        ("TOPPADDING",    (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))

    return [tbl, Spacer(1, 5 * mm)]


def _build_overall_remark(remark: str, styles) -> list:
    """Quoted examiner remark with left accent bar."""
    data = [[
        Table(
            [[""]],
            colWidths=[4],
            rowHeights=[max(30, len(remark) // 4)],
            style=TableStyle([("BACKGROUND", (0, 0), (-1, -1), _C_PRIMARY)]),
        ),
        Paragraph(f'<i>"{remark}"</i>', styles["remark"]),
    ]]
    tbl = Table(data, colWidths=[8, W - 2 * MARGIN - 8])
    tbl.setStyle(TableStyle([
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",  (1, 0), (1, 0), 10),
        ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#f5f3ff")),
        ("BOX", (0, 0), (-1, -1), 0.5, _C_BORDER),
    ]))
    return [
        Paragraph("Examiner's Remark", styles["section_heading"]),
        Spacer(1, 2 * mm),
        tbl,
        Spacer(1, 5 * mm),
    ]


def _build_parameter_table(parameter_scores, styles) -> list:
    """Table of all 5 rubric parameters with score bars and justifications."""
    PARAM_ICONS = {
        "Structure":              "🏗",
        "Content & Accuracy":    "📚",
        "Language & Expression": "✍",
        "Relevance to Question": "🎯",
        "Critical Thinking":     "🧠",
    }

    rows = [
        [
            Paragraph("<b>Parameter</b>", styles["table_header"]),
            Paragraph("<b>Score</b>",     styles["table_header"]),
            Paragraph("<b>Feedback</b>",  styles["table_header"]),
        ]
    ]

    col_w = W - 2 * MARGIN
    for ps in parameter_scores:
        pct   = ps.score / ps.max_score if ps.max_score else 0
        bar_c = _C_SUCCESS if pct >= 0.75 else (_C_WARNING if pct >= 0.5 else _C_DANGER)
        icon  = PARAM_ICONS.get(ps.parameter, "•")

        rows.append([
            Paragraph(f"{icon}  <b>{ps.parameter}</b>", styles["table_cell"]),
            Paragraph(
                f'<font size="14" color="{bar_c.hexval()}"><b>{ps.score}</b></font>'
                f'<font size="8" color="#94a3b8">/{ps.max_score}</font>',
                styles["table_cell"],
            ),
            Paragraph(ps.justification, styles["table_cell_small"]),
        ])

        # Suggestions sub-row
        if ps.suggestions:
            tips = "  •  ".join(ps.suggestions)
            rows.append([
                Paragraph("", styles["table_cell"]),
                Paragraph("", styles["table_cell"]),
                Paragraph(
                    f'<font color="#7c3aed" size="7">💡  {tips}</font>',
                    styles["table_cell_small"],
                ),
            ])

    tbl = Table(
        rows,
        colWidths=[col_w * 0.28, col_w * 0.12, col_w * 0.60],
        repeatRows=1,
    )
    tbl.setStyle(TableStyle([
        # Header row
        ("BACKGROUND",  (0, 0), (-1, 0), _C_PRIMARY),
        ("TEXTCOLOR",   (0, 0), (-1, 0), _C_WHITE),
        ("FONTSIZE",    (0, 0), (-1, 0), 9),
        ("TOPPADDING",  (0, 0), (-1, 0), 6),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        # Data rows
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [_C_WHITE, colors.HexColor("#f8fafc")]),
        ("GRID",        (0, 0), (-1, -1), 0.4, _C_BORDER),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",  (0, 1), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))

    return [
        Paragraph("Parameter Breakdown", styles["section_heading"]),
        Spacer(1, 2 * mm),
        tbl,
        Spacer(1, 6 * mm),
    ]


def _build_bullet_section(title: str, items: list[str], colour, styles) -> list:
    """Generic coloured bullet list section."""
    bullets = [
        Paragraph(
            f'<font color="{colour.hexval()}">▸</font>  {item}',
            styles["bullet"],
        )
        for item in items
    ]
    return KeepTogether([
        Paragraph(title, styles["section_heading"]),
        Spacer(1, 2 * mm),
        *bullets,
        Spacer(1, 5 * mm),
    ]),


def _build_extracted_text(text: str, word_count: int, styles) -> list:
    """OCR-extracted text in a monospace-style box."""
    # Truncate very long answers for report readability
    display_text = text if len(text) <= 3000 else text[:3000] + "\n…[truncated for report]"
    safe = display_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    return [
        Paragraph("Extracted Answer Text", styles["section_heading"]),
        Paragraph(
            f'<font color="#64748b" size="8">{word_count} words detected</font>',
            styles["meta"],
        ),
        Spacer(1, 2 * mm),
        Table(
            [[Paragraph(safe, styles["mono"])]],
            colWidths=[W - 2 * MARGIN],
            style=TableStyle([
                ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#f1f5f9")),
                ("BOX",           (0, 0), (-1, -1), 0.5, _C_BORDER),
                ("TOPPADDING",    (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING",   (0, 0), (-1, -1), 10),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
            ]),
        ),
        Spacer(1, 6 * mm),
    ]


def _build_annotation_section(comments, styles) -> list:
    """Inline annotation comments colour-coded by sentiment."""
    SENTIMENT_COLOURS = {
        "positive": colors.HexColor("#059669"),
        "neutral":  colors.HexColor("#3b82f6"),
        "negative": colors.HexColor("#dc2626"),
    }
    SENTIMENT_ICONS = {"positive": "✓", "neutral": "•", "negative": "✗"}

    rows = [[
        Paragraph("<b>¶</b>",        styles["table_header"]),
        Paragraph("<b>Sentiment</b>", styles["table_header"]),
        Paragraph("<b>Comment</b>",   styles["table_header"]),
    ]]
    for c in comments:
        col = SENTIMENT_COLOURS.get(c.sentiment, colors.black)
        icon = SENTIMENT_ICONS.get(c.sentiment, "•")
        rows.append([
            Paragraph(str(c.paragraph_index + 1), styles["table_cell"]),
            Paragraph(
                f'<font color="{col.hexval()}">{icon}  {c.sentiment}</font>',
                styles["table_cell_small"],
            ),
            Paragraph(c.comment_text, styles["table_cell_small"]),
        ])

    col_w = W - 2 * MARGIN
    tbl = Table(rows, colWidths=[col_w * 0.07, col_w * 0.15, col_w * 0.78], repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0), _C_TEAL),
        ("TEXTCOLOR",   (0, 0), (-1, 0), _C_WHITE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [_C_WHITE, colors.HexColor("#f0fdfa")]),
        ("GRID",        (0, 0), (-1, -1), 0.4, _C_BORDER),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",  (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))

    return [
        Paragraph("Inline Annotations", styles["section_heading"]),
        Spacer(1, 2 * mm),
        tbl,
    ]


# ── Footer ─────────────────────────────────────────────────────────────────

def _draw_footer(canvas, doc):
    """Draw a thin bottom footer with page number and branding."""
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(_C_LIGHT)
    y = 12 * mm
    canvas.drawString(MARGIN, y, "EvalPro — Evaluation Report")
    canvas.drawRightString(W - MARGIN, y, f"Page {doc.page}")
    canvas.restoreState()


# ── Style definitions ─────────────────────────────────────────────────────────

def _build_styles() -> dict:
    base = getSampleStyleSheet()

    def s(name, **kw) -> ParagraphStyle:
        return ParagraphStyle(name, parent=base["Normal"], **kw)

    return {
        "title": s(
            "title",
            fontSize=26, leading=32, textColor=_C_DARK,
            fontName="Helvetica-Bold", alignment=TA_LEFT,
        ),
        "section_heading": s(
            "section_heading",
            fontSize=11, leading=14, textColor=_C_PRIMARY,
            fontName="Helvetica-Bold", spaceBefore=4,
        ),
        "meta": s(
            "meta",
            fontSize=8, leading=11, textColor=_C_MID,
        ),
        "remark": s(
            "remark",
            fontSize=9, leading=13, textColor=_C_DARK,
        ),
        "center": s(
            "center",
            fontSize=10, leading=14, alignment=TA_CENTER,
        ),
        "table_header": s(
            "table_header",
            fontSize=8, leading=10, textColor=_C_WHITE,
            fontName="Helvetica-Bold",
        ),
        "table_cell": s(
            "table_cell",
            fontSize=8, leading=11, textColor=_C_DARK,
        ),
        "table_cell_small": s(
            "table_cell_small",
            fontSize=7, leading=10, textColor=_C_MID,
        ),
        "bullet": s(
            "bullet",
            fontSize=8, leading=12, textColor=_C_DARK,
            leftIndent=12, spaceAfter=3,
        ),
        "mono": s(
            "mono",
            fontSize=7, leading=11, textColor=_C_DARK,
            fontName="Courier",
        ),
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _letter_grade(pct: float) -> str:
    if pct >= 0.8: return "A"
    if pct >= 0.6: return "B"
    if pct >= 0.4: return "C"
    return "D"
