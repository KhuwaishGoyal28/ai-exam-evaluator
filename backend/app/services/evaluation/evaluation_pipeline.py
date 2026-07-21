"""
Evaluation pipeline orchestrator.
Single responsibility: coordinate prompt building + LLM call + result mapping.
"""
from app.models.domain.answer import OCRResult
from app.models.domain.evaluation import EvaluationResult
from app.core.constants import ExamType
from app.core.logging import get_logger
from .prompt_builder import build_evaluation_prompt
from .llm_client import call_evaluation_llm
from .result_mapper import map_llm_response_to_result

logger = get_logger(__name__)


async def run_evaluation_pipeline(
    ocr_result: OCRResult,
    question: str | None,
    exam_type: ExamType = ExamType.UPSC,
) -> EvaluationResult:
    """Full pipeline: OCRResult + exam_type → EvaluationResult."""
    logger.info("evaluation_started", word_count=ocr_result.word_count, exam=exam_type.value)

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
