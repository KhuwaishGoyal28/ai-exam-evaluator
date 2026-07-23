"""
Evaluation pipeline orchestrator.

PRIMARY PATH  (handwritten PDFs / images):
  The Vision agent (vision_client.run_vision_evaluation) already performs
  OCR + evaluation in one combined call and returns the master JSON.
  This pipeline receives that pre-built dict and maps it straight to
  EvaluationResult — NO second LLM call needed.

LEGACY PATH  (text-only PDFs that went through pypdf → no vision call):
  Falls back to the Groq text-eval LLM (llm_client) + old prompt_builder.
"""
from __future__ import annotations

from app.models.domain.answer import OCRResult
from app.models.domain.evaluation import EvaluationResult
from app.core.constants import ExamType
from app.core.logging import get_logger
from .result_mapper import map_vision_result, map_llm_response_to_result

logger = get_logger(__name__)


async def run_evaluation_pipeline(
    ocr_result: OCRResult,
    question: str | None,
    exam_type: ExamType = ExamType.UPSC,
    *,
    vision_json: dict | None = None,   # injected by controller when available
) -> EvaluationResult:
    """
    Full pipeline: OCRResult (+ optional vision_json) → EvaluationResult.

    If vision_json is provided (handwritten upload path), map it directly.
    Otherwise fall back to the text-only LLM evaluation path.
    """
    if vision_json:
        logger.info(
            "evaluation_from_vision_json",
            pages=vision_json.get("document_summary", {}).get("total_pages", "?"),
            exam=exam_type.value,
        )
        result = map_vision_result(vision_json, exam_type=exam_type.value)
        logger.info(
            "evaluation_complete",
            score=result.score_summary.total_score,
            grade=result.score_summary.grade,
        )
        return result

    # ── Legacy text-eval path ─────────────────────────────────────────────
    logger.info(
        "evaluation_text_fallback",
        word_count=ocr_result.word_count,
        exam=exam_type.value,
    )
    from .prompt_builder import build_evaluation_prompt
    from .llm_client import call_evaluation_llm

    system_prompt, user_prompt = build_evaluation_prompt(
        extracted_text=ocr_result.extracted_text,
        question=question,
        paragraphs=ocr_result.paragraph_blocks,
        exam_type=exam_type,
    )
    raw_response = await call_evaluation_llm(system_prompt, user_prompt)
    result = map_llm_response_to_result(raw_response, exam_type=exam_type.value)
    logger.info("evaluation_complete", score=result.total_score, exam=exam_type.value)
    return result
