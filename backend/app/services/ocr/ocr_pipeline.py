"""
OCR pipeline orchestrator — PRIMARY path for handwritten PDFs.

For scanned / handwritten uploads the pipeline now:
  1. Renders the PDF into per-page JPEG images
  2. Calls run_vision_evaluation() with ALL page images in one session
     (one Vision request per page, 8 s delay between pages)
  3. Returns an OCRResult populated from the master JSON
  4. Stores the raw vision_json on the result so the controller can
     pass it directly to the evaluation pipeline (no second LLM call)

For typed-text PDFs (pypdf extracts clean text) the old path still
works unchanged — the controller falls back to the text-eval LLM.
"""
from __future__ import annotations

from app.models.domain.answer import UploadedFile, OCRResult
from app.core.constants import FileType
from app.core.exceptions import OCRExtractionError
from app.core.logging import get_logger
from app.utils.text_utils import split_into_paragraphs, count_words
from .confidence_estimator import estimate_confidence
from .pdf_converter import resolve_pdf_payload
from .vision_client import (
    run_vision_evaluation,
    render_pdf_to_page_images,
    extract_text_via_vision,
)

logger = get_logger(__name__)


async def run_ocr_pipeline(
    uploaded_file: UploadedFile,
    question: str | None = None,
    exam_type: str = "Custom / General",
) -> OCRResult:
    """
    Full OCR pipeline: UploadedFile → OCRResult.

    Handwritten PDF / image  → run_vision_evaluation (master JSON)
    Clean text PDF           → pypdf direct extraction (legacy)

    The OCRResult gains a `vision_json` attribute when the Vision path
    is taken — the controller reads this to skip the second LLM eval call.
    """
    if uploaded_file.file_type == FileType.PDF:
        return await _handle_pdf(uploaded_file, question, exam_type)
    return await _handle_image(uploaded_file, question, exam_type)


# ── PDF handling ──────────────────────────────────────────────────────────────

async def _handle_pdf(
    uploaded_file: UploadedFile,
    question: str | None,
    exam_type: str,
) -> OCRResult:
    pdf_bytes = uploaded_file.content

    # Stage 1 — try pypdf text extraction (fast, no API cost)
    payload, mode = resolve_pdf_payload(pdf_bytes)

    if mode == "text":
        conf = estimate_confidence(payload)          # type: ignore[arg-type]
        if conf < 0 or conf >= 0.55:
            # Clean typed text — use legacy LLM eval path
            logger.info("ocr_mode", mode="pdf_text_direct", confidence=conf)
            return _make_ocr_result(
                text=payload,                        # type: ignore[arg-type]
                vision_json=None,
            )
        logger.info("ocr_mode", mode="pdf_low_conf_vision_fallback", confidence=conf)

    # Stage 2 — render pages and call Vision (scanned / handwritten PDF)
    logger.info("ocr_mode", mode="pdf_vision_all_pages")
    page_images = render_pdf_to_page_images(pdf_bytes)

    if not page_images:
        raise OCRExtractionError(
            "No readable pages found in the uploaded PDF. "
            "Please upload a scanned handwritten PDF."
        )

    vision_json = await run_vision_evaluation(
        page_images=page_images,
        question=question,
        exam_type=exam_type,
    )

    _guard_empty_transcription(vision_json)

    transcribed = (
        vision_json.get("document_summary", {}).get("transcribed_text", "")
    )
    result = _make_ocr_result(text=transcribed, vision_json=vision_json)
    # Attach page images so the controller can forward them to annotation
    result.page_images = page_images           # type: ignore[attr-defined]
    return result


async def _handle_image(
    uploaded_file: UploadedFile,
    question: str | None,
    exam_type: str,
) -> OCRResult:
    """Single-image upload — run Vision on the one page."""
    logger.info("ocr_mode", mode="image_vision_single")
    page_images = [uploaded_file.content]

    vision_json = await run_vision_evaluation(
        page_images=page_images,
        question=question,
        exam_type=exam_type,
    )

    _guard_empty_transcription(vision_json)

    transcribed = (
        vision_json.get("document_summary", {}).get("transcribed_text", "")
    )
    result = _make_ocr_result(text=transcribed, vision_json=vision_json)
    result.page_images = page_images           # type: ignore[attr-defined]
    return result


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_ocr_result(text: str, vision_json: dict | None) -> OCRResult:
    """Build an OCRResult from extracted text; attach vision_json as extra attr."""
    confidence  = estimate_confidence(text)
    paragraphs  = split_into_paragraphs(text)
    word_count  = count_words(text)
    low_conf    = _is_low_confidence(confidence)

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
    # Dynamic attribute — avoids modifying the OCRResult dataclass
    result.vision_json = vision_json           # type: ignore[attr-defined]
    return result


def _guard_empty_transcription(vision_json: dict) -> None:
    """
    Raise a 400-level error when the Vision agent found no handwritten text
    across all pages — prevents sending an empty payload to the evaluator.
    """
    ds = vision_json.get("document_summary", {})
    has_content = ds.get("has_handwritten_content", True)
    transcribed = (ds.get("transcribed_text") or "").strip()
    status      = ds.get("transcription_status", "SUCCESS")

    if not has_content or not transcribed or status == "FAILED":
        logger.warning(
            "ocr_no_handwritten_content",
            status=status,
            has_content=has_content,
        )
        raise OCRExtractionError(
            "No handwritten text was found in the uploaded document. "
            "Please upload a scanned handwritten answer sheet (PDF or image). "
            "Ensure the file is not blank and the handwriting is clearly visible."
        )


def _is_low_confidence(confidence: float) -> bool:
    if confidence < 0:
        return False
    from app.core.constants import OCR_CONFIDENCE_THRESHOLD
    return confidence < OCR_CONFIDENCE_THRESHOLD
