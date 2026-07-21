"""
PDF → text/bytes resolver for the OCR pipeline.
Single responsibility: given PDF bytes, return something the Vision API can consume.

Multi-page support:
  Stage 1 — pypdf text extraction across ALL pages (instant, no API call).
  Stage 2 — embedded XObject image extraction from ALL pages (first image wins per page).
  Stage 3 — send raw PDF bytes directly to Gemini Vision (handles everything else).

Returns:
  (str,   "text")  → full text already extracted; skip Vision
  (bytes, "image") → concatenated JPEG from all pages; send to Vision as image/jpeg
  (bytes, "pdf")   → raw PDF bytes; send to Vision as application/pdf
"""
from __future__ import annotations

import io
from PIL import Image

from app.core.logging import get_logger

logger = get_logger(__name__)

# Minimum character count to accept pypdf text extraction as meaningful
_MIN_TEXT_CHARS = 30


def resolve_pdf_payload(pdf_bytes: bytes) -> tuple[bytes | str, str]:
    """
    Decide the best extraction strategy for this PDF.
    Never raises — always falls back to raw PDF pass-through.
    """
    # Stage 1 — text-based PDF (all pages)
    text = _extract_all_pages_text(pdf_bytes)
    if text:
        logger.info("pdf_resolver", stage=1, mode="text", chars=len(text))
        return (text, "text")

    # Stage 2 — scanned PDF with embedded images (all pages)
    combined_image = _extract_all_pages_images(pdf_bytes)
    if combined_image is not None:
        logger.info("pdf_resolver", stage=2, mode="image")
        return (_to_jpeg_bytes(combined_image), "image")

    # Stage 3 — raw PDF to Gemini Vision
    logger.info("pdf_resolver", stage=3, mode="pdf")
    return (pdf_bytes, "pdf")


# ── Stage implementations ─────────────────────────────────────────────────────

def _extract_all_pages_text(pdf_bytes: bytes) -> str:
    """
    Extract selectable text from every page of the PDF using pypdf.
    Pages are separated by double newlines.
    Returns an empty string if the PDF has no meaningful text.
    """
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(pdf_bytes))
        if not reader.pages:
            return ""

        page_texts: list[str] = []
        for page_num, page in enumerate(reader.pages):
            raw = page.extract_text() or ""
            stripped = raw.strip()
            if stripped:
                page_texts.append(stripped)
                logger.info("pdf_page_text", page=page_num, chars=len(stripped))

        combined = "\n\n".join(page_texts).strip()
        return combined if len(combined) >= _MIN_TEXT_CHARS else ""

    except Exception as exc:
        logger.warning("pdf_text_extract_failed", error=str(exc))
        return ""


def _extract_all_pages_images(pdf_bytes: bytes) -> Image.Image | None:
    """
    Extract the first embedded XObject image from each page.
    Stitch all per-page images vertically into a single tall JPEG.
    Returns None if no embedded images are found on any page.
    """
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(pdf_bytes))
        if not reader.pages:
            return None

        page_images: list[Image.Image] = []

        for page_num, page in enumerate(reader.pages):
            img = _extract_first_image_from_page(page, page_num)
            if img is not None:
                page_images.append(img)

        if not page_images:
            return None

        if len(page_images) == 1:
            return page_images[0]

        return _stack_images_vertically(page_images)

    except Exception as exc:
        logger.warning("pdf_image_extract_failed", error=str(exc))
        return None


def _extract_first_image_from_page(page, page_num: int) -> Image.Image | None:
    """
    Pull the first /XObject /Image from a pypdf page object.
    Single responsibility: one page → one image or None.
    """
    try:
        resources = page.get("/Resources")
        if not resources:
            return None

        xobjects = resources.get("/XObject")
        if not xobjects:
            return None

        for key in xobjects:
            obj = xobjects[key]
            if obj.get("/Subtype") != "/Image":
                continue
            try:
                img = Image.open(io.BytesIO(obj.get_data())).convert("RGB")
                logger.info("pdf_page_image_extracted", page=page_num)
                return img
            except Exception:
                continue  # try next XObject on this page

    except Exception as exc:
        logger.warning("pdf_page_image_failed", page=page_num, error=str(exc))

    return None


def _stack_images_vertically(images: list[Image.Image]) -> Image.Image:
    """
    Stack a list of PIL Images vertically into one tall image.
    All images are scaled to the same width (largest width wins).
    Single responsibility: image list → single combined image.
    """
    max_width = max(img.width for img in images)
    total_height = 0
    resized: list[Image.Image] = []

    for img in images:
        if img.width != max_width:
            ratio  = max_width / img.width
            new_h  = int(img.height * ratio)
            img    = img.resize((max_width, new_h), Image.LANCZOS)
        resized.append(img)
        total_height += img.height

    combined = Image.new("RGB", (max_width, total_height), color=(255, 255, 255))
    y_offset = 0
    for img in resized:
        combined.paste(img, (0, y_offset))
        y_offset += img.height

    return combined


def _to_jpeg_bytes(image: Image.Image, quality: int = 92) -> bytes:
    """Encode a Pillow Image to JPEG bytes."""
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()
