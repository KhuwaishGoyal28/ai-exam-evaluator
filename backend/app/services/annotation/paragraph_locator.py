"""
Computes approximate Y-coordinate positions for each paragraph block
relative to the image height.

Single responsibility: (image_height, num_paragraphs) → list[y_position].

Logic: divide the image into equal horizontal bands per paragraph,
with a top margin to skip headers/question text.
"""

_TOP_MARGIN_RATIO = 0.08   # skip top 8% of image (usually question / page header)
_BOTTOM_MARGIN_RATIO = 0.05


def compute_paragraph_y_positions(
    image_height: int,
    num_paragraphs: int,
) -> list[int]:
    """
    Return a list of Y pixel coordinates (top of each paragraph band).
    Length == num_paragraphs.
    """
    if num_paragraphs <= 0:
        return []

    usable_top = int(image_height * _TOP_MARGIN_RATIO)
    usable_bottom = int(image_height * (1 - _BOTTOM_MARGIN_RATIO))
    usable_height = usable_bottom - usable_top

    band_height = usable_height // num_paragraphs

    return [
        usable_top + i * band_height + band_height // 4
        for i in range(num_paragraphs)
    ]
