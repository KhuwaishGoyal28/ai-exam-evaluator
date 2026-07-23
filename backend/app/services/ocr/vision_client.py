"""
Groq Vision — Combined OCR + Evaluation Agent.

One Vision call per page using the master system prompt.
Returns a structured JSON payload matching the master schema:
  {document_summary, score_summary, page_annotations,
   parameter_breakdown, overall_evaluation}

Free-tier limits (on-demand): 8,000 TPM.
Strategy: compress each page to ≤800px / JPEG-60, one page per call,
8-second delay between calls so TPM budget resets.

Public API:
  run_vision_evaluation(page_images, question, exam_type)
      → dict  (master JSON, merged across all pages)
"""
from __future__ import annotations

import asyncio
import base64
import io
import json
import re

from openai import AsyncOpenAI
from PIL import Image

from app.config import get_settings
from app.core.exceptions import OCRExtractionError, ExternalServiceError
from app.core.logging import get_logger

logger = get_logger(__name__)

_GROQ_BASE_URL      = "https://api.groq.com/openai/v1"
_PAGE_DELAY_SECONDS = 8      # seconds between pages to respect 8k TPM
_MAX_IMAGE_WIDTH    = 800    # px — keeps tokens low while text stays legible
_JPEG_QUALITY       = 60     # enough for OCR, saves ~40% tokens vs 90

# ── Master system prompt ──────────────────────────────────────────────────────

_MASTER_SYSTEM = """\
You are an expert academic evaluator, vision OCR system, and UPSC/IAS essay examiner.
Your task is to evaluate handwritten student assignments, provide precise visual
red-ink annotation coordinates for PDF rendering, score content against standard
evaluation rubrics, and output a structured JSON response.

CRITICAL INSTRUCTIONS:

1. HANDWRITTEN CONTENT FILTERING:
   - Transcribe and evaluate ONLY pen/pencil handwritten content written by the student.
   - Strictly IGNORE all pre-printed text, question prompts, headers, footers, page
     numbers, institution logos, scanner watermarks, and pre-printed margin lines.
   - If the page contains NO handwritten text, set has_handwritten_content: false.

2. PAGE-BY-PAGE RED-INK ANNOTATIONS:
   For every page with handwritten content, pinpoint specific line snippets and assign
   visual examiner annotations:
   - PRAISE / STRENGTHS: Tag strong definitions, vivid hooks, accurate examples
     with TICK mark_symbol and short margin note (e.g. "Sharp definition",
     "Good civilisational grounding", "Good admin lens").
   - CORRECTIONS / SLIPS: Tag spelling mistakes, factual errors, inverted logic
     with CROSS mark_symbol (e.g. "sp? available", "should be 'selfish' not 'selfless'").
   - STRUCTURAL ADVICE: Add MARGIN_BOX for structural callout notes
     (e.g. "Names too many leaders — pick 1-2 and develop in depth").

3. ANNOTATION LOCATION:
   For every annotation provide y_percent (0 = top of page, 100 = bottom) to indicate
   where the snippet appears vertically on the page.
   position must be RIGHT_MARGIN, LEFT_MARGIN, or INLINE.

4. PARAMETER RUBRIC SCORING (score the WHOLE document on this ONE call for page 1,
   skip scoring for subsequent pages but still provide annotations):
   - Introductory competence        (max 8)
   - Lucidity of language           (max 10)
   - Interlinkage between paragraphs(max 8)
   - Clarity of concept & examples  (max 12)
   - Structure of essay             (max 10)
   - Body & alignment with theme    (max 12)
   - Commitment to topic            (max 8)
   - Concluding remarks             (max 10)
   - Fresh insights                 (max 8)
   - Visionary perspectives         (max 6)
   - Social & public-service orientation (max 6)
   - Adherence to word limit        (max 2)
   Total = 100. Calibration: 65-72 = competent complete essay; 80+ = exceptional.
   Provide 1-sentence examiner_remark per parameter.

5. OVERALL SUMMARY & RESUBMISSION CHECKLIST:
   Write a constructive summary paragraph explaining the score.
   Provide 3-5 concrete "BEFORE YOU RESUBMIT" checklist items.

OUTPUT FORMAT:
Return ONLY valid JSON — no prose, no markdown outside the JSON block.

{
  "document_summary": {
    "total_pages": 0,
    "estimated_word_count": 0,
    "target_word_count": 1200,
    "transcription_status": "SUCCESS",
    "has_handwritten_content": true,
    "transcribed_text": "full handwritten text of this page only"
  },
  "score_summary": {
    "total_score": 65,
    "max_score": 100,
    "grade": "B",
    "performance_status": "Strong Draft"
  },
  "page_annotations": [
    {
      "page_number": 1,
      "annotations": [
        {
          "type": "PRAISE",
          "target_snippet": "exact quoted text from student handwriting",
          "mark_symbol": "TICK",
          "annotation_text": "Sharp definition",
          "location": {"y_percent": 18, "position": "RIGHT_MARGIN"}
        }
      ]
    }
  ],
  "parameter_breakdown": [
    {
      "parameter_name": "Introductory competence",
      "marks_obtained": 6,
      "max_marks": 8,
      "examiner_remark": "Strong hook and clear thesis by line 3."
    }
  ],
  "overall_evaluation": {
    "summary_remarks": "A strong draft with a clear spine...",
    "actionable_resubmission_checklist": [
      "Fix the Gita line: use 'selfish' not 'selfless'.",
      "Add a counter-view paragraph of 120-150 words.",
      "Develop two examples in depth instead of single-line mentions."
    ]
  }
}
"""


# ── Public entry point ────────────────────────────────────────────────────────

async def run_vision_evaluation(
    page_images: list[bytes],
    question: str | None,
    exam_type: str,
) -> dict:
    """
    Send each page image individually to Groq Vision using the master prompt.
    Returns a merged master-schema dict with all pages' annotations combined.
    """
    if not page_images:
        raise OCRExtractionError("No page images provided for vision evaluation.")

    total_pages = len(page_images)
    merged: dict = {}

    for page_num, img_bytes in enumerate(page_images):
        if page_num > 0:
            logger.info("vision_page_delay", page=page_num, wait_s=_PAGE_DELAY_SECONDS)
            await asyncio.sleep(_PAGE_DELAY_SECONDS)

        page_result = await _evaluate_single_page(
            img_bytes=img_bytes,
            page_num=page_num,
            total_pages=total_pages,
            question=question,
            exam_type=exam_type,
        )
        logger.info("vision_page_done", page=page_num + 1)

        if page_num == 0:
            # First page carries the full evaluation + scoring
            merged = page_result
            # Ensure page_annotations list is initialised
            if "page_annotations" not in merged:
                merged["page_annotations"] = []
        else:
            # Subsequent pages — merge annotations only
            extra_annotations = page_result.get("page_annotations", [])
            merged["page_annotations"].extend(extra_annotations)

            # Merge transcribed text
            extra_text = (
                page_result.get("document_summary", {}).get("transcribed_text", "")
            )
            if extra_text:
                existing = merged.get("document_summary", {}).get("transcribed_text", "")
                merged["document_summary"]["transcribed_text"] = (
                    f"{existing}\n\n--- PAGE BREAK ---\n\n{extra_text}"
                )

            # Update word count
            ds = merged.get("document_summary", {})
            extra_wc = page_result.get("document_summary", {}).get("estimated_word_count", 0)
            ds["estimated_word_count"] = ds.get("estimated_word_count", 0) + extra_wc
            ds["total_pages"] = total_pages

    # Fix total_pages in final result
    if "document_summary" in merged:
        merged["document_summary"]["total_pages"] = total_pages

    return merged


async def _evaluate_single_page(
    img_bytes: bytes,
    page_num: int,
    total_pages: int,
    question: str | None,
    exam_type: str,
) -> dict:
    """Send one compressed page image to Groq Vision, return parsed JSON dict."""
    compressed = _compress_image(img_bytes)
    b64 = base64.b64encode(compressed).decode()

    is_first_page = (page_num == 0)
    scoring_note = (
        "This is PAGE 1 — provide FULL parameter scoring and overall evaluation."
        if is_first_page
        else f"This is PAGE {page_num + 1} of {total_pages}. "
             "Provide ONLY page_annotations for this page. "
             "Set parameter_breakdown to [] and overall_evaluation fields to empty strings."
    )

    user_content = [
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
        },
        {
            "type": "text",
            "text": (
                f"EXAM TYPE: {exam_type}\n"
                f"TOPIC / QUESTION: {question or 'Not provided'}\n"
                f"PAGE: {page_num + 1} of {total_pages}\n\n"
                f"{scoring_note}\n\n"
                "Evaluate the handwritten content on this page. "
                "Return ONLY the JSON schema described in your system prompt."
            ),
        },
    ]

    raw = await _call_groq_vision(user_content)
    return _parse_json_robust(raw, page_num=page_num + 1)


# ── Groq Vision call ──────────────────────────────────────────────────────────

async def _call_groq_vision(user_content: list[dict]) -> str:
    settings = get_settings()
    client = AsyncOpenAI(
        api_key=settings.groq_api_key,
        base_url=_GROQ_BASE_URL,
    )
    try:
        response = await client.chat.completions.create(
            model=settings.groq_vision_model,
            max_tokens=settings.groq_vision_max_tokens,
            messages=[
                {"role": "system", "content": _MASTER_SYSTEM},
                {"role": "user",   "content": user_content},
            ],
        )
        text = (response.choices[0].message.content or "").strip()
        if not text:
            raise OCRExtractionError("Groq Vision returned empty response.")
        return text
    except OCRExtractionError:
        raise
    except Exception as exc:
        logger.error("groq_vision_failed", error=str(exc))
        raise ExternalServiceError(f"Groq Vision call failed: {exc}") from exc


# ── JSON parsing ──────────────────────────────────────────────────────────────

def _parse_json_robust(raw: str, page_num: int = 1) -> dict:
    """Try several strategies to extract valid JSON from the Vision response."""
    # 1. Strip markdown fences
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    cleaned = re.sub(r"\s*```$", "", cleaned)

    # 2. Direct parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # 3. Extract outermost { ... }
    start = cleaned.find("{")
    if start != -1:
        depth = 0
        for i, ch in enumerate(cleaned[start:], start):
            if ch == "{":   depth += 1
            elif ch == "}": depth -= 1
            if depth == 0:
                try:
                    return json.loads(cleaned[start: i + 1])
                except json.JSONDecodeError:
                    break

    # 4. Fallback — return minimal valid structure so the pipeline continues
    logger.warning("vision_json_parse_failed", page=page_num, preview=raw[:200])
    return _fallback_page_result(page_num)


def _fallback_page_result(page_num: int) -> dict:
    return {
        "document_summary": {
            "total_pages": 1,
            "estimated_word_count": 0,
            "target_word_count": 1200,
            "transcription_status": "FAILED",
            "has_handwritten_content": False,
            "transcribed_text": "",
        },
        "score_summary": {
            "total_score": 0,
            "max_score": 100,
            "grade": "D",
            "performance_status": "Needs Work",
        },
        "page_annotations": [{"page_number": page_num, "annotations": []}],
        "parameter_breakdown": [],
        "overall_evaluation": {
            "summary_remarks": "Could not process this page.",
            "actionable_resubmission_checklist": [],
        },
    }


# ── Image rendering helpers ───────────────────────────────────────────────────

def _compress_image(image_bytes: bytes) -> bytes:
    """Resize to ≤800px wide and re-encode as JPEG-60. Reduces tokens ~40%."""
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        w, h = img.size
        if w > _MAX_IMAGE_WIDTH:
            ratio = _MAX_IMAGE_WIDTH / w
            img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=_JPEG_QUALITY)
        compressed = buf.getvalue()
        logger.info("image_compressed",
                    original_kb=len(image_bytes) // 1024,
                    compressed_kb=len(compressed) // 1024)
        return compressed
    except Exception as exc:
        logger.warning("image_compress_failed", error=str(exc))
        return image_bytes


def render_pdf_to_page_images(pdf_bytes: bytes) -> list[bytes]:
    """
    Convert every page of a PDF to a JPEG bytes object.
    Tries three strategies: embedded images → pdf2image → PyMuPDF.
    """
    images = _extract_embedded_images(pdf_bytes)
    if images:
        return images
    images = _rasterise_with_pdf2image(pdf_bytes)
    if images:
        return images
    return _rasterise_with_pymupdf(pdf_bytes)


def _extract_embedded_images(pdf_bytes: bytes) -> list[bytes]:
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(pdf_bytes))
        result: list[bytes] = []
        for page in reader.pages:
            resources = page.get("/Resources")
            if not resources:
                continue
            xobjs = resources.get("/XObject")
            if not xobjs:
                continue
            for key in xobjs:
                obj = xobjs[key]
                if obj.get("/Subtype") != "/Image":
                    continue
                try:
                    img = Image.open(io.BytesIO(obj.get_data())).convert("RGB")
                    buf = io.BytesIO()
                    img.save(buf, format="JPEG", quality=90)
                    result.append(buf.getvalue())
                    break
                except Exception:
                    continue
        if result:
            logger.info("pdf_embedded_images", pages=len(result))
        return result
    except Exception as exc:
        logger.warning("pdf_embedded_failed", error=str(exc))
        return []


def _rasterise_with_pdf2image(pdf_bytes: bytes) -> list[bytes]:
    try:
        from pdf2image import convert_from_bytes
        pil_images = convert_from_bytes(pdf_bytes, dpi=120)
        result = []
        for img in pil_images:
            buf = io.BytesIO()
            img.convert("RGB").save(buf, format="JPEG", quality=85)
            result.append(buf.getvalue())
        logger.info("pdf2image_rasterised", pages=len(result))
        return result
    except ImportError:
        return []
    except Exception as exc:
        logger.warning("pdf2image_failed", error=str(exc))
        return []


def _rasterise_with_pymupdf(pdf_bytes: bytes) -> list[bytes]:
    try:
        import fitz
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        result = []
        for page in doc:
            mat = fitz.Matrix(120 / 72, 120 / 72)
            pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
            result.append(pix.tobytes("jpeg"))
        doc.close()
        logger.info("pymupdf_rasterised", pages=len(result))
        return result
    except ImportError:
        return []
    except Exception as exc:
        logger.warning("pymupdf_failed", error=str(exc))
        return []


# ── Legacy shims (used by old ocr_pipeline.py path for plain images) ──────────

async def extract_text_via_vision(image_bytes: bytes) -> str:
    """Shim: extract handwritten text only from a single image."""
    result = await run_vision_evaluation([image_bytes], question=None, exam_type="Custom / General")
    return result.get("document_summary", {}).get("transcribed_text", "")


async def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Shim: render PDF pages and extract handwritten text."""
    pages = render_pdf_to_page_images(pdf_bytes)
    if not pages:
        return ""
    result = await run_vision_evaluation(pages, question=None, exam_type="Custom / General")
    return result.get("document_summary", {}).get("transcribed_text", "")
