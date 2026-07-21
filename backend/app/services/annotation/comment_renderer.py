"""
Renders annotation comments as margin overlays on a Pillow Image.
Single responsibility: (Image, comments, y_positions) → annotated Image.

Design:
  - Comments appear in a right-side margin panel.
  - Each comment has a coloured left accent bar matching sentiment.
  - A thin connector line links the comment to its paragraph position.
  - Y-collision detection prevents comments from overlapping.
"""
from __future__ import annotations

import textwrap
from PIL import Image, ImageDraw, ImageFont
from app.models.domain.evaluation import AnnotationComment
from app.core.logging import get_logger

logger = get_logger(__name__)

# Sentiment colour palette (RGB)
_SENTIMENT_COLOURS: dict[str, tuple[int, int, int]] = {
    "positive": (16, 185, 129),   # emerald
    "neutral":  (99, 102, 241),   # indigo
    "negative": (239, 68, 68),    # red
}
_BG_COLOURS: dict[str, tuple[int, int, int]] = {
    "positive": (236, 253, 245),  # emerald-50
    "neutral":  (238, 242, 255),  # indigo-50
    "negative": (254, 242, 242),  # red-50
}

_MARGIN_WIDTH    = 360   # pixels for the right margin panel
_MARGIN_BG       = (248, 249, 252)
_SEPARATOR_COLOUR= (226, 232, 240)

_FONT_SIZE       = 20
_LINE_SPACING    = 8
_BOX_V_PAD       = 10
_BOX_H_PAD       = 14
_ACCENT_WIDTH    = 4
_MIN_COMMENT_GAP = 12   # minimum vertical gap between comment boxes


def render_comments_on_image(
    image: Image.Image,
    comments: list[AnnotationComment],
    y_positions: list[int],
) -> Image.Image:
    """
    Return a new wider image with comments rendered in the right margin.
    Does not mutate the input image.
    """
    canvas = _build_canvas(image)
    draw = ImageDraw.Draw(canvas)
    font = _load_font(_FONT_SIZE)

    placed = _place_comments_no_overlap(comments, y_positions, image.height, draw, font)

    for (comment, y_anchor, box_h) in placed:
        colour    = _SENTIMENT_COLOURS.get(comment.sentiment, _SENTIMENT_COLOURS["neutral"])
        bg_colour = _BG_COLOURS.get(comment.sentiment, _BG_COLOURS["neutral"])
        margin_x  = image.width + _BOX_H_PAD

        _draw_connector(draw, image.width, y_anchor, colour)
        _draw_comment_box(draw, font, comment.comment_text, margin_x, y_anchor, colour, bg_colour, box_h)

    return canvas


# ── canvas helpers ────────────────────────────────────────────────────────────

def _build_canvas(image: Image.Image) -> Image.Image:
    """Expand canvas horizontally to accommodate the margin panel."""
    total_width = image.width + _MARGIN_WIDTH
    canvas = Image.new("RGB", (total_width, image.height), color=_MARGIN_BG)
    canvas.paste(image, (0, 0))

    draw = ImageDraw.Draw(canvas)
    # Separator line
    draw.line(
        [(image.width, 0), (image.width, image.height)],
        fill=_SEPARATOR_COLOUR,
        width=2,
    )
    # Margin header
    header_font = _load_font(18)
    draw.text(
        (image.width + _BOX_H_PAD, 12),
        "AI Annotations",
        fill=(148, 163, 184),
        font=header_font,
    )
    draw.line(
        [(image.width + _BOX_H_PAD, 36), (image.width + _MARGIN_WIDTH - _BOX_H_PAD, 36)],
        fill=_SEPARATOR_COLOUR,
        width=1,
    )
    return canvas


# ── layout ────────────────────────────────────────────────────────────────────

def _place_comments_no_overlap(
    comments: list[AnnotationComment],
    y_positions: list[int],
    image_height: int,
    draw: ImageDraw.ImageDraw,
    font: ImageFont.ImageFont,
) -> list[tuple[AnnotationComment, int, int]]:
    """
    Assign final Y positions to comments, pushing down when boxes would overlap.
    Returns list of (comment, y_top, box_height).
    """
    result: list[tuple[AnnotationComment, int, int]] = []
    next_available_y = 50   # start below the "AI Annotations" header

    sorted_comments = sorted(
        comments,
        key=lambda c: y_positions[c.paragraph_index]
            if c.paragraph_index < len(y_positions) else image_height,
    )

    for comment in sorted_comments:
        box_h = _measure_box_height(comment.comment_text, draw, font)
        raw_y = _get_y_for_paragraph(comment.paragraph_index, y_positions, image_height)
        y = max(raw_y, next_available_y)
        # Clamp to image height
        y = min(y, image_height - box_h - 8)
        result.append((comment, y, box_h))
        next_available_y = y + box_h + _MIN_COMMENT_GAP

    return result


def _measure_box_height(text: str, draw: ImageDraw.ImageDraw, font: ImageFont.ImageFont) -> int:
    """Calculate the pixel height of a comment box for the given text."""
    available_text_width = _MARGIN_WIDTH - _BOX_H_PAD * 2 - _ACCENT_WIDTH - 8
    wrapped = _wrap_text_px(text, draw, font, available_text_width)
    line_h  = _FONT_SIZE + _LINE_SPACING
    return _BOX_V_PAD * 2 + line_h * max(len(wrapped), 1)


def _get_y_for_paragraph(
    paragraph_index: int,
    y_positions: list[int],
    image_height: int,
) -> int:
    if paragraph_index < len(y_positions):
        return y_positions[paragraph_index]
    if y_positions:
        return y_positions[-1] + 60
    return image_height // 4


# ── drawing ───────────────────────────────────────────────────────────────────

def _draw_connector(
    draw: ImageDraw.ImageDraw,
    x_image_edge: int,
    y: int,
    colour: tuple[int, int, int],
) -> None:
    """Draw a small dashed horizontal connector from the answer body to the margin."""
    for x in range(x_image_edge, x_image_edge + _BOX_H_PAD, 4):
        draw.line([(x, y + 12), (x + 2, y + 12)], fill=colour, width=1)


def _draw_comment_box(
    draw: ImageDraw.ImageDraw,
    font: ImageFont.ImageFont,
    text: str,
    x: int,
    y: int,
    colour: tuple[int, int, int],
    bg_colour: tuple[int, int, int],
    box_h: int,
) -> None:
    """Draw a comment box with coloured background, accent bar, and wrapped text."""
    box_w = _MARGIN_WIDTH - _BOX_H_PAD * 2

    # Background rounded rect (approximate with rectangle)
    draw.rectangle([(x, y), (x + box_w, y + box_h)], fill=bg_colour)

    # Left accent bar
    draw.rectangle([(x, y), (x + _ACCENT_WIDTH, y + box_h)], fill=colour)

    # Text
    text_x = x + _ACCENT_WIDTH + 8
    text_y = y + _BOX_V_PAD
    available_w = box_w - _ACCENT_WIDTH - 16
    lines = _wrap_text_px(text, draw, font, available_w)
    line_h = _FONT_SIZE + _LINE_SPACING

    for i, line in enumerate(lines):
        draw.text((text_x, text_y + i * line_h), line, fill=colour, font=font)


# ── text helpers ──────────────────────────────────────────────────────────────

def _wrap_text_px(
    text: str,
    draw: ImageDraw.ImageDraw,
    font: ImageFont.ImageFont,
    max_width: int,
) -> list[str]:
    """Word-wrap text to fit within max_width pixels. Returns list of line strings."""
    words  = text.split()
    lines  : list[str] = []
    current = ""

    for word in words:
        test  = f"{current} {word}".strip()
        bbox  = draw.textbbox((0, 0), test, font=font)
        width = bbox[2] - bbox[0]
        if width <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word

    if current:
        lines.append(current)

    return lines if lines else [""]


def _load_font(size: int) -> ImageFont.ImageFont:
    """Load system font with fallback to PIL default."""
    font_paths = [
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibri.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for path in font_paths:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    logger.warning("font_fallback", size=size)
    return ImageFont.load_default()
