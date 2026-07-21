"""
Renders extracted text onto a clean A4-style canvas for annotation.
Single responsibility: (text, paragraphs) → Pillow Image with readable text layout.

Used when no scan image is available (text-based PDFs).
"""
from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont
from app.core.logging import get_logger

logger = get_logger(__name__)

# Canvas dimensions — A4 proportions at 150 dpi
_CANVAS_WIDTH  = 1240
_CANVAS_HEIGHT = 1754

# Layout margins
_MARGIN_LEFT   = 80
_MARGIN_TOP    = 120
_MARGIN_RIGHT  = 80
_TEXT_WIDTH    = _CANVAS_WIDTH - _MARGIN_LEFT - _MARGIN_RIGHT

# Colours
_BG_COLOUR         = (252, 252, 252)    # near-white
_TEXT_COLOUR       = (30, 30, 30)       # near-black
_PARA_NUM_COLOUR   = (160, 160, 200)    # muted indigo
_RULE_COLOUR       = (220, 220, 230)    # light separator
_HEADER_COLOUR     = (99, 102, 241)     # brand indigo
_LINE_NUM_COLOUR   = (180, 180, 180)    # muted gray

# Font sizes
_HEADER_FONT_SIZE  = 28
_BODY_FONT_SIZE    = 26
_PARA_NUM_SIZE     = 18


def render_text_canvas(
    extracted_text: str,
    paragraph_blocks: list[str],
) -> Image.Image:
    """
    Render extracted text onto a clean A4 canvas and return a Pillow Image.
    Paragraphs are numbered and separated with thin rules for easy annotation.
    """
    canvas = Image.new("RGB", (_CANVAS_WIDTH, _CANVAS_HEIGHT), color=_BG_COLOUR)
    draw = ImageDraw.Draw(canvas)

    body_font   = _load_font(_BODY_FONT_SIZE)
    header_font = _load_font(_HEADER_FONT_SIZE)
    para_font   = _load_font(_PARA_NUM_SIZE)

    _draw_header(draw, header_font)
    _draw_content(draw, body_font, para_font, paragraph_blocks)
    _draw_page_border(draw)

    logger.info("text_canvas_rendered", paragraphs=len(paragraph_blocks))
    return canvas


def _draw_header(draw: ImageDraw.ImageDraw, font: ImageFont.ImageFont) -> None:
    """Draw a branded header at the top of the canvas."""
    # Header background strip
    draw.rectangle([(0, 0), (_CANVAS_WIDTH, 80)], fill=(99, 102, 241))
    draw.text(
        (_MARGIN_LEFT, 22),
        "AnswerCheck — Extracted Answer Text",
        fill=(255, 255, 255),
        font=font,
    )
    # Subtle bottom accent
    draw.rectangle([(0, 80), (_CANVAS_WIDTH, 84)], fill=(165, 180, 252))


def _draw_content(
    draw: ImageDraw.ImageDraw,
    body_font: ImageFont.ImageFont,
    para_font: ImageFont.ImageFont,
    paragraphs: list[str],
) -> None:
    """Render each paragraph with a number label and separator."""
    y = _MARGIN_TOP + 20
    max_y = _CANVAS_HEIGHT - 80   # bottom margin

    for idx, para in enumerate(paragraphs):
        if y >= max_y:
            break

        # Paragraph number bubble
        draw.text(
            (_MARGIN_LEFT - 50, y),
            f"¶{idx + 1}",
            fill=_PARA_NUM_COLOUR,
            font=para_font,
        )

        # Wrap and draw text
        lines = _wrap_text(para, body_font, _TEXT_WIDTH, draw)
        for line in lines:
            if y >= max_y:
                break
            draw.text((_MARGIN_LEFT, y), line, fill=_TEXT_COLOUR, font=body_font)
            y += _BODY_FONT_SIZE + 8   # line height

        # Paragraph separator
        y += 14
        if idx < len(paragraphs) - 1:
            draw.line(
                [(_MARGIN_LEFT, y), (_CANVAS_WIDTH - _MARGIN_RIGHT, y)],
                fill=_RULE_COLOUR,
                width=1,
            )
            y += 18


def _wrap_text(
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
    draw: ImageDraw.ImageDraw,
) -> list[str]:
    """
    Wrap text to fit within max_width pixels.
    Returns a list of line strings.
    """
    words = text.split()
    lines: list[str] = []
    current = ""

    for word in words:
        test = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        w = bbox[2] - bbox[0]
        if w <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word

    if current:
        lines.append(current)

    return lines or [""]


def _draw_page_border(draw: ImageDraw.ImageDraw) -> None:
    """Draw a subtle page border for a document look."""
    draw.rectangle(
        [(4, 4), (_CANVAS_WIDTH - 4, _CANVAS_HEIGHT - 4)],
        outline=(220, 220, 230),
        width=2,
    )


def _load_font(size: int) -> ImageFont.ImageFont:
    """Load system font with fallback."""
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
    return ImageFont.load_default()
