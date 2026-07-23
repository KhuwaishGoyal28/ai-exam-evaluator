"""
Evaluate controller — orchestrates the full pipeline.
Single responsibility: call services in order, assemble the response DTO.

Supabase folder structure per evaluation:
  evaluations/{job_id}/
    original.{ext}    ← raw upload
    annotated.jpg     ← annotated image
    report.json       ← complete evaluation report
"""
import json
import uuid

from app.models.domain.answer import UploadedFile
from app.models.responses.evaluate import (
    EvaluateResponse,
    EvaluationResultOut,
    ParameterScoreOut,
    EssayParameterScoreOut,
    AnnotationCommentOut,
)
from app.services.ocr import run_ocr_pipeline
from app.services.evaluation import run_evaluation_pipeline
from app.services.annotation import run_annotation_pipeline
from app.services.storage import store_original_file, store_annotated_file, store_report
from app.core.constants import ExamType
from app.core.logging import get_logger

logger = get_logger(__name__)


async def process_answer_submission(
    uploaded_file: UploadedFile,
    question: str | None,
    exam_type: ExamType = ExamType.UPSC,
) -> EvaluateResponse:
    """
    Full pipeline:
      1. Store original file   → evaluations/{job_id}/original.{ext}
      2. OCR extraction
      3. LLM rubric evaluation
      4. Image annotation
      5. Store annotated image → evaluations/{job_id}/annotated.jpg
      6. Build + store report  → evaluations/{job_id}/report.json
      7. Return EvaluateResponse
    """
    job_id = str(uuid.uuid4())
    logger.info("job_started", job_id=job_id, filename=uploaded_file.filename, exam=exam_type.value)

    # ── 1. Store original ──────────────────────────────────────────────────
    original_stored = store_original_file(
        uploaded_file.content, job_id, uploaded_file.mime_type
    )

    # ── 2. OCR ─────────────────────────────────────────────────────────────
    ocr_result = await run_ocr_pipeline(uploaded_file)

    # ── 3. Evaluation ──────────────────────────────────────────────────────
    evaluation_result = await run_evaluation_pipeline(ocr_result, question, exam_type)

    # ── 4. Annotation ──────────────────────────────────────────────────────
    annotated_bytes = await run_annotation_pipeline(uploaded_file, ocr_result, evaluation_result)

    # ── 5. Store annotated image ───────────────────────────────────────────
    annotated_stored = store_annotated_file(annotated_bytes, job_id)

    # ── 6. Build structured response DTO ──────────────────────────────────
    response = _build_response(
        job_id=job_id,
        original_url=original_stored.secure_url,
        annotated_url=annotated_stored.secure_url,
        report_url="",
        ocr_result=ocr_result,
        evaluation_result=evaluation_result,
    )

    # ── 7. Store full report JSON ──────────────────────────────────────────
    report_json = _build_report_json(response, question, exam_type)
    report_stored = store_report(report_json, job_id)
    response.report_url = report_stored.secure_url

    logger.info(
        "job_complete",
        job_id=job_id,
        score=evaluation_result.total_score,
        original=original_stored.secure_url,
        annotated=annotated_stored.secure_url,
        report=report_stored.secure_url,
    )
    return response


# ── private helpers ────────────────────────────────────────────────────────


def _build_response(
    job_id: str,
    original_url: str,
    annotated_url: str,
    report_url: str,
    ocr_result,
    evaluation_result,
) -> EvaluateResponse:
    """Assemble the flat response DTO from domain objects."""

    # Map essay parameter scores if present
    essay_scores_out = [
        EssayParameterScoreOut(
            parameter=eps.parameter,
            score=eps.score,
            max_score=eps.max_score,
            examiner_remark=eps.examiner_remark,
            suggestions=eps.suggestions,
        )
        for eps in evaluation_result.essay_parameter_scores
    ]

    # Map standard parameter scores if present
    standard_scores_out = [
        ParameterScoreOut(
            parameter=ps.parameter,
            score=ps.score,
            max_score=ps.max_score,
            justification=ps.justification,
            suggestions=ps.suggestions,
        )
        for ps in evaluation_result.parameter_scores
    ]

    return EvaluateResponse(
        job_id=job_id,
        original_file_url=original_url,
        annotated_file_url=annotated_url,
        report_url=report_url,
        extracted_text=ocr_result.extracted_text,
        word_count=ocr_result.word_count,
        ocr_low_confidence=ocr_result.low_confidence,
        evaluation=EvaluationResultOut(
            parameter_scores=standard_scores_out,
            essay_parameter_scores=essay_scores_out,
            before_resubmit=evaluation_result.before_resubmit,
            total_score=evaluation_result.total_score,
            max_total_score=evaluation_result.max_total_score,
            overall_remark=evaluation_result.overall_remark,
            exam_type=evaluation_result.exam_type,
            strengths=evaluation_result.strengths,
            improvements=evaluation_result.improvements,
        ),
        annotation_comments=[
            AnnotationCommentOut(
                paragraph_index=c.paragraph_index,
                comment_text=c.comment_text,
                sentiment=c.sentiment,
            )
            for c in evaluation_result.annotation_comments
        ],
    )


def _build_report_json(
    response: EvaluateResponse,
    question: str | None,
    exam_type: ExamType,
) -> str:
    """
    Build a self-contained JSON report suitable for download/archival.
    Includes all evaluation data, file URLs, and metadata.
    """
    ev = response.evaluation

    # Build parameter scores section — essay or standard
    if ev.essay_parameter_scores:
        param_section = [
            {
                "parameter":       eps.parameter,
                "score":           eps.score,
                "max_score":       eps.max_score,
                "examiner_remark": eps.examiner_remark,
                "suggestions":     eps.suggestions,
            }
            for eps in ev.essay_parameter_scores
        ]
    else:
        param_section = [
            {
                "parameter":     ps.parameter,
                "score":         ps.score,
                "max_score":     ps.max_score,
                "justification": ps.justification,
                "suggestions":   ps.suggestions,
            }
            for ps in ev.parameter_scores
        ]

    report = {
        "job_id":    response.job_id,
        "exam_type": exam_type.value,
        "question":  question or "",
        "files": {
            "original":  response.original_file_url,
            "annotated": response.annotated_file_url,
        },
        "ocr": {
            "extracted_text": response.extracted_text,
            "word_count":     response.word_count,
            "low_confidence": response.ocr_low_confidence,
        },
        "evaluation": {
            "total_score":      ev.total_score,
            "max_total_score":  ev.max_total_score,
            "overall_remark":   ev.overall_remark,
            "strengths":        ev.strengths,
            "improvements":     ev.improvements,
            "before_resubmit":  ev.before_resubmit,
            "parameter_scores": param_section,
        },
        "annotation_comments": [
            {
                "paragraph_index": c.paragraph_index,
                "comment_text":    c.comment_text,
                "sentiment":       c.sentiment,
            }
            for c in response.annotation_comments
        ],
    }
    return json.dumps(report, indent=2, ensure_ascii=False)
