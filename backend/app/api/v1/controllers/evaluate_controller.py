"""
Evaluate controller — orchestrates the full pipeline.

Steps:
  1. Store original file
  2. OCR + Vision evaluation (combined in one call)
  3. Map Vision JSON → EvaluationResult
  4. Build checked PDF with PyMuPDF red-ink overlays
  5. Store checked PDF
  6. Build + store report JSON
  7. Return EvaluateResponse
"""
from __future__ import annotations

import json
import uuid

from app.models.domain.answer import UploadedFile
from app.models.responses.evaluate import (
    EvaluateResponse,
    EvaluationSummaryOut,
    RubricItemOut,
    TeacherAnnotationOut,
    AnnotationCommentOut,
    ScoreSummaryOut,
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
    job_id = str(uuid.uuid4())
    logger.info("job_started", job_id=job_id,
                filename=uploaded_file.filename, exam=exam_type.value)

    # 1. Store original
    original_stored = store_original_file(
        uploaded_file.content, job_id, uploaded_file.mime_type
    )

    # 2. OCR — Vision agent performs OCR + evaluation together
    ocr_result = await run_ocr_pipeline(
        uploaded_file,
        question=question,
        exam_type=exam_type.value,
    )
    vision_json = getattr(ocr_result, "vision_json", None)
    page_images = getattr(ocr_result, "page_images", None)

    # 3. Map to EvaluationResult
    evaluation_result = await run_evaluation_pipeline(
        ocr_result,
        question=question,
        exam_type=exam_type,
        vision_json=vision_json,
    )

    # 4. Build annotated PDF
    annotated_bytes = await run_annotation_pipeline(
        uploaded_file,
        ocr_result,
        evaluation_result,
        page_images=page_images,
        question=question,
        exam_type=exam_type.value,
        job_id=job_id,
    )

    # 5. Store annotated output
    is_pdf       = page_images is not None
    a_mime       = "application/pdf" if is_pdf else "image/jpeg"
    a_ext        = "pdf" if is_pdf else "jpg"
    ann_stored   = store_annotated_file(
        annotated_bytes, job_id, mime_type=a_mime, extension=a_ext
    )

    # 6. Build response DTO
    response = _build_response(
        job_id=job_id,
        original_url=original_stored.secure_url,
        annotated_url=ann_stored.secure_url,
        report_url="",
        ocr_result=ocr_result,
        evaluation_result=evaluation_result,
    )

    # 7. Store report JSON
    report_json   = _build_report_json(response, question, exam_type)
    report_stored = store_report(report_json, job_id)
    response.report_url = report_stored.secure_url

    logger.info("job_complete", job_id=job_id,
                marks=evaluation_result.evaluation_summary.total_marks,
                grade=evaluation_result.evaluation_summary.grade)
    return response


# ── Response builder ──────────────────────────────────────────────────────────

def _build_response(
    job_id: str,
    original_url: str,
    annotated_url: str,
    report_url: str,
    ocr_result,
    evaluation_result,
) -> EvaluateResponse:
    es = evaluation_result.evaluation_summary

    # Rubric items
    rubric_out = {
        k: RubricItemOut(marks=v.marks, max=v.max, remark=v.remark)
        for k, v in es.rubric.items()
    }

    # Teacher annotations
    ann_out = [
        TeacherAnnotationOut(
            page=a.page,
            paragraph=a.paragraph,
            sentence=a.sentence,
            annotation_type=a.annotation_type,
            comment=a.comment,
        )
        for a in es.annotations
    ]

    # Legacy AnnotationComment (kept for any frontend that still reads it)
    legacy_comments = [
        AnnotationCommentOut(
            paragraph_index=c.paragraph_index,
            comment_text=c.comment_text,
            sentiment=c.sentiment,
        )
        for c in evaluation_result.annotation_comments
    ]

    summary_out = EvaluationSummaryOut(
        student_name=es.student_name,
        subject=es.subject,
        has_handwritten_content=es.has_handwritten_content,
        transcribed_text=es.transcribed_text,
        total_marks=es.total_marks,
        max_marks=es.max_marks,
        grade=es.grade,
        performance_level=es.performance_level,
        rubric=rubric_out,
        strengths=es.strengths,
        weaknesses=es.weaknesses,
        remarks=es.remarks,
        annotations=ann_out,
        total_pages=es.total_pages,
    )

    return EvaluateResponse(
        job_id=job_id,
        original_file_url=original_url,
        annotated_file_url=annotated_url,
        report_url=report_url,
        extracted_text=ocr_result.extracted_text,
        word_count=ocr_result.word_count,
        ocr_low_confidence=ocr_result.low_confidence,
        evaluation_summary=summary_out,
        annotation_comments=legacy_comments,
        total_marks=es.total_marks,
        max_marks=es.max_marks,
        grade=es.grade,
        performance_level=es.performance_level,
    )


# ── Report JSON builder ───────────────────────────────────────────────────────

def _build_report_json(
    response: EvaluateResponse,
    question: str | None,
    exam_type: ExamType,
) -> str:
    es = response.evaluation_summary
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
            "total_pages":           es.total_pages,
            "has_handwritten":       es.has_handwritten_content,
        },
        "evaluation": {
            "student_name":     es.student_name,
            "subject":          es.subject,
            "total_marks":      es.total_marks,
            "max_marks":        es.max_marks,
            "grade":            es.grade,
            "performance_level": es.performance_level,
            "rubric":           {k: {"marks": v.marks, "max": v.max,
                                     "remark": v.remark}
                                 for k, v in es.rubric.items()},
            "strengths":        es.strengths,
            "weaknesses":       es.weaknesses,
            "remarks":          es.remarks,
        },
        "annotations": [
            {
                "page": a.page, "paragraph": a.paragraph,
                "sentence": a.sentence, "type": a.annotation_type,
                "comment": a.comment,
            }
            for a in es.annotations
        ],
    }
    return json.dumps(report, indent=2, ensure_ascii=False)
