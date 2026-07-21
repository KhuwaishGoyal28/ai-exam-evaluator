"""
OCR pipeline orchestrator.
Single responsibility: coordinate file → text extraction → OCRResult.

PDF handling uses a three-stage resolver (see pdf_converter.py):
  text PDF  → extract text directly, skip Vision
  image PDF → extract embedded image, send to Vision as JPEG
  other PDF → send raw PDF to GPT-4o Vision (handles vector/complex PDFs)
"""
from app.models.domain.answer import UploadedFile, OCRResult
from app.core.constants import FileType
from app.core.logging import get_logger
from app.utils.text_utils import split_into_paragraphs, count_words
from .pdf_converter import resolve_pdf_payload
from .vision_client import extract_text_via_vision, extract_text_from_pdf
from .confidence_estimator import estimate_confidence

logger = get_logger(__name__)


async def run_ocr_pipeline(uploaded_file: UploadedFile) -> OCRResult:
    """
    Full OCR pipeline: UploadedFile → OCRResult.
    Steps:
      1. Resolve the file to a usable payload (image bytes / PDF bytes / raw text).
      2. If already text (text PDF), skip Vision.
         If image or PDF bytes, call the appropriate Vision extractor.
      3. Estimate confidence, split paragraphs, count words.
      4. Return OCRResult.
    """
    raw_text = await _extract_text(uploaded_file)
    confidence = estimate_confidence(raw_text)
    paragraphs = split_into_paragraphs(raw_text)
    word_count = count_words(raw_text)
    low_confidence = _is_low_confidence(confidence)

    logger.info(
        "ocr_complete",
        word_count=word_count,
        confidence=round(confidence, 3),
        low_confidence=low_confidence,
    )

    return OCRResult(
        extracted_text=raw_text,
        confidence=confidence,
        word_count=word_count,
        paragraph_blocks=paragraphs,
        low_confidence=low_confidence,
    )


async def _extract_text(uploaded_file: UploadedFile) -> str:
    """Dispatch to the right extraction path based on file type."""
    if uploaded_file.file_type == FileType.PDF:
        return await _extract_from_pdf(uploaded_file.content)
    # Plain image — send directly to Vision
    return await extract_text_via_vision(uploaded_file.content)


async def _extract_from_pdf(pdf_bytes: bytes) -> str:
    """
    Use three-stage resolver to get the best extraction mode,
    then call the right Vision function (or return text directly).
    """
    payload, mode = resolve_pdf_payload(pdf_bytes)

    if mode == "text":
        # Text already extracted by pypdf — no Vision call needed
        logger.info("ocr_mode", mode="pdf_text_direct")
        return payload  # type: ignore[return-value]

    if mode == "image":
        logger.info("ocr_mode", mode="pdf_image_vision")
        return await extract_text_via_vision(payload)  # type: ignore[arg-type]

    # mode == "pdf" — send raw PDF to GPT-4o Vision
    logger.info("ocr_mode", mode="pdf_raw_vision")
    return await extract_text_from_pdf(payload)  # type: ignore[arg-type]


def _is_low_confidence(confidence: float) -> bool:
    """Return True when confidence is below the acceptable threshold."""
    if confidence < 0:
        return False  # provider gave no score; treat as acceptable
    from app.core.constants import OCR_CONFIDENCE_THRESHOLD
    return confidence < OCR_CONFIDENCE_THRESHOLD
