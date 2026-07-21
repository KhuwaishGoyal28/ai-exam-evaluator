"""
Renders a score banner at the top of the annotated image.
Single responsibility: adds a summary strip showing total score + grade.
"""
from PIL import Image, ImageDraw, ImageFont
from app.models.domain.evaluation import EvaluationResult
from app.services.annotation.comment_renderer import _load_font

_BANNER_HEIGHT = 70
_BANNER_COLOUR = (40, 40, 40)
_TEXT_COLOUR = (255, 255, 255)
_ACCENT_COLOURS = {
    "A": (46, 160, 67),   # green
    "B": (100, 160, 240), # blue
    "C": (240, 180, 0),   # amber
    "D": (200, 60, 40),   # red
}


def add_score_banner(image: Image.Image, result: EvaluationResult) -> Image.Image:
    """
    Prepend a dark banner strip with score and grade to the top of the image.
    Returns a new image; does not mutate the input.
    """
    grade = _compute_grade(result.total_score, result.max_total_score)
    accent = _ACCENT_COLOURS.get(grade, _ACCENT_COLOURS["C"])

    banner = Image.new("RGB", (image.width, _BANNER_HEIGHT), color=_BANNER_COLOUR)
    draw = ImageDraw.Draw(banner)

    # Left accent strip
    draw.rectangle([(0, 0), (6, _BANNER_HEIGHT)], fill=accent)

    font_large = _load_font(28)
    font_small = _load_font(18)

    score_text = f"Score: {result.total_score} / {result.max_total_score}"
    grade_text = f"Grade: {grade}"
    draw.text((20, 10), score_text, fill=_TEXT_COLOUR, font=font_large)
    draw.text((20, 44), grade_text, fill=accent, font=font_small)

    remark_preview = result.overall_remark[:80] + ("…" if len(result.overall_remark) > 80 else "")
    draw.text((280, 26), remark_preview, fill=(200, 200, 200), font=font_small)

    combined = Image.new("RGB", (image.width, image.height + _BANNER_HEIGHT))
    combined.paste(banner, (0, 0))
    combined.paste(image, (0, _BANNER_HEIGHT))
    return combined


def _compute_grade(score: int, max_score: int) -> str:
    """Map a score percentage to a letter grade."""
    pct = (score / max_score) * 100 if max_score else 0
    if pct >= 80:
        return "A"
    if pct >= 60:
        return "B"
    if pct >= 40:
        return "C"
    return "D"
