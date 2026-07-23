"""
OCR pipeline orchestrator.

Decision tree:
  PDF with extractable text (pypdf confidence ≥ 0.55)
    → use text directly, skip Vision, fall back to text-eval LLM

  PDF with embedded images / scanned / low-confidence text
    → render pages to JPEG → Groq Vision OCR+eval → vision_json

  Single image upload
    → Groq Vision OCR+eval → vision_json

  If Vision returns no recognisable content (typed doc sent to Vision):
    → fall back to pypdf text + text-eval LLM (never raise 422 for this)
"""
from __future__ import annotations

from app.models.domain.answer import UploadedFile, OCRResult
from app.core.constants import FileType
from app.core.exceptions import OCRExtractionError
from app.core.logging import get_logger
from app.utils.text_utils import split_into_paragraphs, count_words
from .confidence_estimator import estimate_confidence
from .pdf_converter import resolve_pdf_payload
from .vision_client import run_vision_evaluation, render_pdf_to_page_images

logger = get_logger(__name__)


async def run_ocr_pipeline(
    uploaded_file: UploadedFile,
    question: str | None = None,
    exam_type: str = "Custom / General",
) -> OCRResult:
    if uploaded_file.file_type == FileType.PDF:
        return await _handle_pdf(uploaded_file, question, exam_type)
    return await _handle_image(uploaded_file, question, exam_type)


# ── PDF ───────────────────────────────────────────────────────────────────────

async def _handle_pdf(
    uploaded_file: UploadedFile,
    question: str | None,
    exam_type: str,
) -> OCRResult:
    pdf_bytes = uploaded_file.content

    # Stage 1 — try pypdf text extraction (instant, free)
    payload, mode = resolve_pdf_payload(pdf_bytes)

    if mode == "text":
        conf = estimate_confidence(payload)          # type: ignore[arg-type]
        if conf < 0 or conf >= 0.55:
            # Clean typed text PDF — use legacy text-eval LLM path, no Vision call
            logger.info("ocr_mode", mode="pdf_text_direct", confidence=conf)
            return _make_ocr_result(text=payload, vision_json=None)   # type: ignore[arg-type]
        logger.info("ocr_mode", mode="pdf_low_conf_trying_vision", confidence=conf)

    # Stage 2 — render pages and send to Vision
    logger.info("ocr_mode", mode="pdf_vision_all_pages")
    page_images = render_pdf_to_page_images(pdf_bytes)

    if not page_images:
        # No image pages found — fall back to whatever pypdf got
        if mode == "text" and payload:
            logger.warning("pdf_no_images_using_pypdf_text")
            return _make_ocr_result(text=payload, vision_json=None)   # type: ignore[arg-type]
        raise OCRExtractionError(
            "Could not extract any pages from the uploaded PDF. "
            "Please ensure it is not password-protected or corrupted."
        )

    vision_json = await run_vision_evaluation(
        page_images=page_images,
        question=question,
        exam_type=exam_type,
    )

    transcribed = _extract_transcribed_text(vision_json)

    # If Vision found no handwritten content, fall back to pypdf text (typed doc)
    if not transcribed:
        if mode == "text" and payload:
            logger.info("vision_no_handwriting_fallback_pypdf")
            # Still attach page_images so annotation pipeline can render a checked PDF
            result = _make_ocr_result(text=payload, vision_json=None)   # type: ignore[arg-type]
            result.page_images = page_images   # type: ignore[attr-defined]
            return result
        logger.warning("vision_no_handwriting_no_text_fallback")
        # Return vision_json as-is so the evaluator can still produce a result
        # (it will score 0 but won't crash with a 422)
        result = _make_ocr_result(text="", vision_json=vision_json)
        result.page_images = page_images       # type: ignore[attr-defined]
        return result

    result = _make_ocr_result(text=transcribed, vision_json=vision_json)
    result.page_images = page_images           # type: ignore[attr-defined]
    return result


# ── Image ─────────────────────────────────────────────────────────────────────

async def _handle_image(
    uploaded_file: UploadedFile,
    question: str | None,
    exam_type: str,
) -> OCRResult:
    logger.info("ocr_mode", mode="image_vision_single")
    page_images = [uploaded_file.content]

    vision_json = await run_vision_evaluation(
        page_images=page_images,
        question=question,
        exam_type=exam_type,
    )

    transcribed = _extract_transcribed_text(vision_json)

    if not transcribed:
        # Image has no recognisable handwriting — still proceed, don't raise 422
        logger.warning("vision_image_no_handwriting")

    result = _make_ocr_result(text=transcribed, vision_json=vision_json)
    result.page_images = page_images           # type: ignore[attr-defined]
    return result


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_transcribed_text(vision_json: dict) -> str:
    """
    Extract the transcribed handwritten text from a Vision response.

    The new schema places it at the top level:  vision_json["transcribed_text"]
    The old master-schema placed it at:         vision_json["document_summary"]["transcribed_text"]
    Both are checked so old and new responses work.
    """
    # Primary location (new teacher-evaluation schema)
    top_level = (vision_json.get("transcribed_text") or "").strip()
    if top_level:
        return top_level

    # Fallback: old master-schema location
    nested = (
        vision_json.get("document_summary", {}).get("transcribed_text") or ""
    ).strip()
    return nested


def _make_ocr_result(text: str, vision_json: dict | None) -> OCRResult:
    """Build an OCRResult; attach vision_json as a dynamic attribute."""
    confidence = estimate_confidence(text)
    paragraphs = split_into_paragraphs(text)
    word_count = count_words(text)
    low_conf   = _is_low_confidence(confidence)

    logger.info(
        "ocr_complete",
        word_count=word_count,
        confidence=round(confidence, 3),
        low_confidence=low_conf,
        has_vision_json=vision_json is not None,
    )

    result = OCRResult(
        extracted_text=text,
        confidence=confidence,
        word_count=word_count,
        paragraph_blocks=paragraphs,
        low_confidence=low_conf,
    )
    result.vision_json = vision_json   # type: ignore[attr-defined]
    return result


def _is_low_confidence(confidence: float) -> bool:
    if confidence < 0:
        return False
    from app.core.constants import OCR_CONFIDENCE_THRESHOLD
    return confidence < OCR_CONFIDENCE_THRESHOLD
