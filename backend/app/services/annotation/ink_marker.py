"""
Draws teacher-style red ink marks directly on an answer image.
Single responsibility: Image + marks list → annotated Image.

Marks mimic real exam checking:
  - Red underlines under problematic phrases (negative sentiment)
  - Green tick (✓) beside positive paragraphs
  - Red cross (✗) beside weak paragraphs
  - Wavy red underline under the last line of a poor paragraph
  - Circle around the score at the end
  - Diagonal arrow pointing to the margin comment
"""
from __future__ import annotations
import math
from PIL import Image, ImageDraw, ImageFont
from app.models.domain.evaluation import AnnotationComment
from app.core.logging import get_logger

logger = get_logger(__name__)

# Ink colours
_RED        = (220, 38, 38)    # teacher red
_GREEN      = (22, 163, 74)    # tick green
_BLUE       = (37, 99, 235)    # neutral blue
_PENCIL     = (100, 100, 120)  # pencil grey for subtle marks

_LINE_W  = 3   # ink stroke width
_TICK_SZ = 28  # tick/cross glyph size


def draw_ink_marks(
    image: Image.Image,
    comments: list[AnnotationComment],
    y_positions: list[int],
    page_width: int,
) -> Image.Image:
    """
    Draw teacher ink marks on the answer body (left side of the image).
    Returns a new image; does not mutate the input.
    """
    marked = image.copy()
    draw   = ImageDraw.Draw(marked)
    font   = _load_ink_font(22)
    small  = _load_ink_font(16)

    for comment in comments:
        y = _get_y(comment.paragraph_index, y_positions, image.height)
        _draw_mark_for_comment(draw, comment, y, page_width, font, small)

    return marked


def _draw_mark_for_comment(
    draw: ImageDraw.ImageDraw,
    comment: AnnotationComment,
    y: int,
    page_width: int,
    font: ImageFont.ImageFont,
    small: ImageFont.ImageFont,
) -> None:
    """Draw the appropriate ink mark for one comment at Y position."""
    left_margin = 18   # left edge for symbols
    text_start  = 58   # where the answer text begins (approximate)
    text_end    = page_width - 20

    if comment.sentiment == "positive":
        _draw_tick(draw, left_margin, y, font)
        _draw_green_underline(draw, text_start, y + 28, text_end)

    elif comment.sentiment == "negative":
        _draw_cross(draw, left_margin, y, font)
        _draw_wavy_underline(draw, text_start, y + 28, text_end, _RED)
        # Short red margin note indicator arrow
        _draw_arrow(draw, text_end + 8, y + 14, text_end + 30, y + 14, _RED)

    else:  # neutral
        _draw_dot(draw, left_margin + 4, y + 14)
        _draw_straight_underline(draw, text_start, y + 28, text_end // 2, _BLUE)


def _draw_tick(draw, x: int, y: int, font) -> None:
    """Draw a teacher green tick ✓."""
    draw.text((x, y), "✓", fill=_GREEN, font=font)


def _draw_cross(draw, x: int, y: int, font) -> None:
    """Draw a teacher red cross ✗."""
    draw.text((x, y), "✗", fill=_RED, font=font)


def _draw_dot(draw, x: int, y: int) -> None:
    """Draw a small neutral bullet dot."""
    r = 5
    draw.ellipse([(x - r, y - r), (x + r, y + r)], fill=_PENCIL)


def _draw_green_underline(
    draw: ImageDraw.ImageDraw, x1: int, y: int, x2: int
) -> None:
    """Solid green underline for positive sections."""
    draw.line([(x1, y), (x2, y)], fill=_GREEN, width=2)


def _draw_straight_underline(
    draw: ImageDraw.ImageDraw, x1: int, y: int, x2: int, colour: tuple
) -> None:
    draw.line([(x1, y), (x2, y)], fill=colour, width=2)


def _draw_wavy_underline(
    draw: ImageDraw.ImageDraw, x1: int, y: int, x2: int, colour: tuple
) -> None:
    """
    Draw a wavy underline (squiggly red line) to indicate errors.
    Approximated with short alternating up/down line segments.
    """
    amplitude = 4
    period    = 12
    x = x1
    toggle = 1
    while x < x2 - period:
        nx = min(x + period, x2)
        ny = y + amplitude * toggle
        draw.line([(x, y), (nx, ny)], fill=colour, width=_LINE_W)
        toggle = -toggle
        x = nx


def _draw_arrow(
    draw: ImageDraw.ImageDraw,
    x1: int, y1: int, x2: int, y2: int,
    colour: tuple,
) -> None:
    """Draw a small arrow line pointing right."""
    draw.line([(x1, y1), (x2, y2)], fill=colour, width=2)
    # Arrowhead
    draw.polygon(
        [(x2, y2), (x2 - 8, y2 - 5), (x2 - 8, y2 + 5)],
        fill=colour,
    )


def _get_y(paragraph_index: int, y_positions: list[int], image_height: int) -> int:
    if paragraph_index < len(y_positions):
        return y_positions[paragraph_index]
    if y_positions:
        return min(y_positions[-1] + 60 * (paragraph_index - len(y_positions) + 2), image_height - 40)
    return image_height // 4


def _load_ink_font(size: int) -> ImageFont.ImageFont:
    for path in [
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibri.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()
