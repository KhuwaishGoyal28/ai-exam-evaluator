"""
Evaluate controller — orchestrates the full pipeline.
Single responsibility: call services in order, assemble the response DTO.

Supabase folder structure per evaluation:
  evaluations/{job_id}/
    original.{ext}      ← raw upload
    checked.pdf         ← PyMuPDF red-ink annotated PDF  (primary)
    annotated.jpg       ← PIL JPEG fallback               (legacy)
    report.json         ← complete evaluation report
"""
from __future__ import annotations

import json
import uuid

from app.models.domain.answer import UploadedFile
from app.models.responses.evaluate import (
    EvaluateResponse,
    EvaluationResultOut,
    DocumentSummaryOut,
    ScoreSummaryOut,
    PageAnnotationOut,
    AnnotationLocationOut,
    ParameterBreakdownOut,
    OverallEvaluationOut,
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
      1. Store original file
      2. OCR (Vision agent — returns master JSON for handwritten PDFs)
      3. Evaluation (maps vision JSON directly; no second LLM call)
      4. Annotation (PyMuPDF checked PDF for handwritten; JPEG for legacy)
      5. Store annotated output
      6. Build + store report JSON
      7. Return EvaluateResponse
    """
    job_id = str(uuid.uuid4())
    logger.info("job_started", job_id=job_id,
                filename=uploaded_file.filename, exam=exam_type.value)

    # ── 1. Store original ──────────────────────────────────────────────────
    original_stored = store_original_file(
        uploaded_file.content, job_id, uploaded_file.mime_type
    )

    # ── 2. OCR ─────────────────────────────────────────────────────────────
    ocr_result = await run_ocr_pipeline(
        uploaded_file,
        question=question,
        exam_type=exam_type.value,
    )

    # vision_json and page_images are attached dynamically by ocr_pipeline
    vision_json  = getattr(ocr_result, "vision_json",  None)
    page_images  = getattr(ocr_result, "page_images",  None)

    # ── 3. Evaluation ──────────────────────────────────────────────────────
    evaluation_result = await run_evaluation_pipeline(
        ocr_result,
        question=question,
        exam_type=exam_type,
        vision_json=vision_json,
    )

    # ── 4. Annotation ──────────────────────────────────────────────────────
    annotated_bytes = await run_annotation_pipeline(
        uploaded_file,
        ocr_result,
        evaluation_result,
        page_images=page_images,
        question=question,
        exam_type=exam_type.value,
        job_id=job_id,
    )

    # ── 5. Store annotated output ──────────────────────────────────────────
    # Primary path produces a PDF; legacy path produces a JPEG
    is_pdf_output  = page_images is not None
    annotated_mime = "application/pdf" if is_pdf_output else "image/jpeg"
    annotated_ext  = "pdf" if is_pdf_output else "jpg"
    annotated_stored = store_annotated_file(
        annotated_bytes, job_id,
        mime_type=annotated_mime,
        extension=annotated_ext,
    )

    # ── 6. Build response DTO ──────────────────────────────────────────────
    response = _build_response(
        job_id=job_id,
        original_url=original_stored.secure_url,
        annotated_url=annotated_stored.secure_url,
        report_url="",
        ocr_result=ocr_result,
        evaluation_result=evaluation_result,
    )

    # ── 7. Store report JSON ───────────────────────────────────────────────
    report_json   = _build_report_json(response, question, exam_type)
    report_stored = store_report(report_json, job_id)
    response.report_url = report_stored.secure_url

    logger.info(
        "job_complete",
        job_id=job_id,
        score=evaluation_result.score_summary.total_score,
        grade=evaluation_result.score_summary.grade,
        annotated=annotated_stored.secure_url,
    )
    return response


# ── Response builder ───────────────────────────────────────────────────────────

def _build_response(
    job_id: str,
    original_url: str,
    annotated_url: str,
    report_url: str,
    ocr_result,
    evaluation_result,
) -> EvaluateResponse:
    """Assemble the EvaluateResponse DTO from domain objects."""
    ev = evaluation_result

    # ── ScoreSummaryOut (required field — always populate) ────────────────
    ss = ev.score_summary
    score_summary_out = ScoreSummaryOut(
        total_score=ss.total_score,
        max_score=ss.max_score,
        grade=ss.grade,
        performance_status=ss.performance_status,
    )

    # ── DocumentSummaryOut ────────────────────────────────────────────────
    ds = ev.document_summary
    doc_summary_out = DocumentSummaryOut(
        total_pages=ds.total_pages,
        estimated_word_count=ds.estimated_word_count,
        target_word_count=ds.target_word_count,
        transcription_status=ds.transcription_status,
        has_handwritten_content=ds.has_handwritten_content,
        transcribed_text=ds.transcribed_text,
    )

    # ── PageAnnotationsOut ────────────────────────────────────────────────
    page_ann_out = [
        PageAnnotationOut(
            annotation_type=a.annotation_type,
            target_snippet=a.target_snippet,
            mark_symbol=a.mark_symbol,
            annotation_text=a.annotation_text,
            location=AnnotationLocationOut(
                y_percent=a.location.y_percent,
                position=a.location.position,
            ),
            page_number=a.page_number,
        )
        for a in ev.page_annotations
    ]

    # ── ParameterBreakdownOut ─────────────────────────────────────────────
    param_bd_out = [
        ParameterBreakdownOut(
            parameter_name=pb.parameter_name,
            marks_obtained=pb.marks_obtained,
            max_marks=pb.max_marks,
            examiner_remark=pb.examiner_remark,
        )
        for pb in ev.parameter_breakdown
    ]

    # ── OverallEvaluationOut ──────────────────────────────────────────────
    oe = ev.overall_evaluation
    overall_out = OverallEvaluationOut(
        summary_remarks=oe.summary_remarks,
        actionable_resubmission_checklist=oe.actionable_resubmission_checklist,
    )

    # ── Legacy rubric fields ──────────────────────────────────────────────
    standard_scores_out = [
        ParameterScoreOut(
            parameter=ps.parameter,
            score=ps.score,
            max_score=ps.max_score,
            justification=ps.justification,
            suggestions=ps.suggestions,
        )
        for ps in ev.parameter_scores
    ]
    essay_scores_out = [
        EssayParameterScoreOut(
            parameter=eps.parameter,
            score=eps.score,
            max_score=eps.max_score,
            examiner_remark=eps.examiner_remark,
            suggestions=eps.suggestions,
        )
        for eps in ev.essay_parameter_scores
    ]
    legacy_comments_out = [
        AnnotationCommentOut(
            paragraph_index=c.paragraph_index,
            comment_text=c.comment_text,
            sentiment=c.sentiment,
        )
        for c in ev.annotation_comments
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
            document_summary=doc_summary_out,
            score_summary=score_summary_out,         # ← always present now
            page_annotations=page_ann_out,
            parameter_breakdown=param_bd_out,
            overall_evaluation=overall_out,
            parameter_scores=standard_scores_out,
            essay_parameter_scores=essay_scores_out,
            before_resubmit=ev.before_resubmit,
            exam_type=ev.exam_type,
            strengths=ev.strengths,
            improvements=ev.improvements,
        ),
        annotation_comments=legacy_comments_out,
    )


# ── Report JSON builder ───────────────────────────────────────────────────────

def _build_report_json(
    response: EvaluateResponse,
    question: str | None,
    exam_type: ExamType,
) -> str:
    ev = response.evaluation
    ss = ev.score_summary

    report = {
        "job_id":    response.job_id,
        "exam_type": exam_type.value,
        "question":  question or "",
        "files": {
            "original":  response.original_file_url,
            "annotated": response.annotated_file_url,
        },
        "ocr": {
            "extracted_text":        response.extracted_text,
            "word_count":            response.word_count,
            "low_confidence":        response.ocr_low_confidence,
            "total_pages":           ev.document_summary.total_pages,
            "has_handwritten":       ev.document_summary.has_handwritten_content,
            "transcription_status":  ev.document_summary.transcription_status,
        },
        "score_summary": {
            "total_score":        ss.total_score,
            "max_score":          ss.max_score,
            "grade":              ss.grade,
            "performance_status": ss.performance_status,
        },
        "parameter_breakdown": [
            {
                "parameter_name": pb.parameter_name,
                "marks_obtained": pb.marks_obtained,
                "max_marks":      pb.max_marks,
                "examiner_remark": pb.examiner_remark,
            }
            for pb in ev.parameter_breakdown
        ],
        "overall_evaluation": {
            "summary_remarks":               ev.overall_evaluation.summary_remarks,
            "actionable_resubmission_checklist":
                ev.overall_evaluation.actionable_resubmission_checklist,
        },
        "page_annotations": [
            {
                "page_number":     a.page_number,
                "annotation_type": a.annotation_type,
                "target_snippet":  a.target_snippet,
                "mark_symbol":     a.mark_symbol,
                "annotation_text": a.annotation_text,
                "y_percent":       a.location.y_percent,
                "position":        a.location.position,
            }
            for a in ev.page_annotations
        ],
        # Legacy fields (populated for text-PDF fallback path)
        "legacy_parameter_scores": [
            {
                "parameter":     ps.parameter,
                "score":         ps.score,
                "max_score":     ps.max_score,
                "justification": ps.justification,
            }
            for ps in ev.parameter_scores
        ],
    }
    return json.dumps(report, indent=2, ensure_ascii=False)
