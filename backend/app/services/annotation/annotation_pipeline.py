"""
Annotation pipeline orchestrator.

PRIMARY PATH (handwritten PDF):
  Uses checked_pdf_builder (PyMuPDF) to stamp red-ink overlays using
  y_percent coordinates from page_annotations onto the original page images,
  then appends the score sheet. Returns PDF bytes.

LEGACY PATH (image upload / text PDF):
  Falls back to the old PIL-based comment overlay + score banner.
  Returns JPEG bytes.
"""
from __future__ import annotations

import io
from PIL import Image

from app.models.domain.answer import UploadedFile, OCRResult
from app.models.domain.evaluation import EvaluationResult
from app.core.constants import FileType
from app.core.exceptions import AnnotationError
from app.core.logging import get_logger

logger = get_logger(__name__)


async def run_annotation_pipeline(
    uploaded_file: UploadedFile,
    ocr_result: OCRResult,
    evaluation_result: EvaluationResult,
    *,
    page_images: list[bytes] | None = None,  # raw JPEG bytes per page
    question: str | None = None,
    exam_type: str = "Custom / General",
    job_id: str = "",
) -> bytes:
    """
    Return annotated output bytes.

    If page_images are provided (handwritten PDF path):
      → Build a proper checked PDF with PyMuPDF red-ink overlays.
    Otherwise:
      → Fall back to PIL-based JPEG annotation (legacy path).
    """
    try:
        if page_images:
            return await _run_pdf_annotation(
                page_images, evaluation_result, question, exam_type, job_id
            )
        return await _run_legacy_annotation(uploaded_file, ocr_result, evaluation_result)

    except Exception as exc:
        logger.error("annotation_failed", error=str(exc))
        raise AnnotationError(f"Annotation pipeline failed: {exc}") from exc


# ── Primary: PyMuPDF checked-PDF path ────────────────────────────────────────

async def _run_pdf_annotation(
    page_image_bytes: list[bytes],
    evaluation_result: EvaluationResult,
    question: str | None,
    exam_type: str,
    job_id: str,
) -> bytes:
    """Convert raw JPEG page bytes → PIL Images, build checked PDF."""
    from .checked_pdf_builder import build_checked_pdf

    pil_pages: list[Image.Image] = []
    for img_bytes in page_image_bytes:
        pil_pages.append(Image.open(io.BytesIO(img_bytes)).convert("RGB"))

    pdf_bytes = build_checked_pdf(
        page_images=pil_pages,
        evaluation=evaluation_result,
        question=question,
        exam_type=exam_type,
        job_id=job_id,
    )
    logger.info("annotation_pdf_complete", size_kb=len(pdf_bytes) // 1024)
    return pdf_bytes


# ── Legacy: PIL JPEG annotation path ─────────────────────────────────────────

async def _run_legacy_annotation(
    uploaded_file: UploadedFile,
    ocr_result: OCRResult,
    evaluation_result: EvaluationResult,
) -> bytes:
    from app.utils.image_utils import (
        load_image_from_bytes, image_to_bytes,
        resize_if_too_large, get_image_dimensions,
    )
    from app.services.ocr.pdf_converter import resolve_pdf_payload
    from .paragraph_locator import compute_paragraph_y_positions
    from .comment_renderer import render_comments_on_image
    from .score_banner import add_score_banner
    from .text_canvas_renderer import render_text_canvas

    if uploaded_file.file_type != FileType.PDF:
        base_image = load_image_from_bytes(uploaded_file.content)
    else:
        payload, mode = resolve_pdf_payload(uploaded_file.content)
        if mode == "image":
            base_image = load_image_from_bytes(payload)
        else:
            base_image = render_text_canvas(
                extracted_text=ocr_result.extracted_text,
                paragraph_blocks=ocr_result.paragraph_blocks,
            )

    base_image  = resize_if_too_large(base_image, max_dimension=2000)
    _, height   = get_image_dimensions(base_image)
    y_positions = compute_paragraph_y_positions(
        image_height=height,
        num_paragraphs=len(ocr_result.paragraph_blocks),
    )

    annotated = render_comments_on_image(
        image=base_image,
        comments=evaluation_result.annotation_comments,
        y_positions=y_positions,
    )
    final        = add_score_banner(annotated, evaluation_result)
    result_bytes = image_to_bytes(final, fmt="JPEG")
    logger.info("annotation_legacy_complete", size_kb=len(result_bytes) // 1024)
    return result_bytes
