"""
Annotation pipeline orchestrator.
Single responsibility: coordinate base image resolution, comment overlay, banner.
"""
from __future__ import annotations

from PIL import Image
from app.models.domain.answer import UploadedFile, OCRResult
from app.models.domain.evaluation import EvaluationResult
from app.core.constants import FileType
from app.core.exceptions import AnnotationError
from app.core.logging import get_logger
from app.utils.image_utils import (
    load_image_from_bytes,
    image_to_bytes,
    resize_if_too_large,
    get_image_dimensions,
)
from app.services.ocr.pdf_converter import resolve_pdf_payload
from .paragraph_locator import compute_paragraph_y_positions
from .comment_renderer import render_comments_on_image
from .score_banner import add_score_banner
from .text_canvas_renderer import render_text_canvas

logger = get_logger(__name__)


async def run_annotation_pipeline(
    uploaded_file: UploadedFile,
    ocr_result: OCRResult,
    evaluation_result: EvaluationResult,
) -> bytes:
    """
    Full annotation pipeline:
      1. Resolve base image (scan, embedded PDF image, or rendered text canvas).
      2. Resize to manageable dimensions.
      3. Compute per-paragraph Y positions.
      4. Overlay annotation comments in the right margin.
      5. Add score banner at the top.
      6. Return JPEG bytes.
    """
    try:
        base_image = _resolve_base_image(uploaded_file, ocr_result)
        base_image = resize_if_too_large(base_image, max_dimension=2000)
        _, height = get_image_dimensions(base_image)

        y_positions = compute_paragraph_y_positions(
            image_height=height,
            num_paragraphs=len(ocr_result.paragraph_blocks),
        )

        annotated = render_comments_on_image(
            image=base_image,
            comments=evaluation_result.annotation_comments,
            y_positions=y_positions,
        )

        final = add_score_banner(annotated, evaluation_result)
        result_bytes = image_to_bytes(final, fmt="JPEG")

        logger.info("annotation_complete", output_size_bytes=len(result_bytes))
        return result_bytes

    except Exception as exc:
        logger.error("annotation_failed", error=str(exc))
        raise AnnotationError(f"Annotation pipeline failed: {exc}") from exc


def _resolve_base_image(
    uploaded_file: UploadedFile,
    ocr_result: OCRResult,
) -> Image.Image:
    """
    Return a Pillow Image to annotate.

    Decision tree:
      - Uploaded image → use directly.
      - PDF with embedded scan → extract the scan image.
      - Text-based PDF (no scan) → render extracted text onto a clean canvas.
    """
    if uploaded_file.file_type != FileType.PDF:
        return load_image_from_bytes(uploaded_file.content)

    payload, mode = resolve_pdf_payload(uploaded_file.content)

    if mode == "image":
        logger.info("annotation_base", source="pdf_embedded_image")
        return load_image_from_bytes(payload)  # type: ignore[arg-type]

    # Text-based or vector PDF — render extracted text to a readable canvas
    logger.info("annotation_base", source="text_canvas")
    return render_text_canvas(
        extracted_text=ocr_result.extracted_text,
        paragraph_blocks=ocr_result.paragraph_blocks,
    )
