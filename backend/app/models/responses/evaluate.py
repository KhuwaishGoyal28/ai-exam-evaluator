"""
Pydantic response schemas for the /evaluate endpoint.
Matches the master JSON schema from the Vision agent.
"""
from __future__ import annotations
from pydantic import BaseModel, Field
from app.core.constants import RubricParameter


# ── Master-schema output types ────────────────────────────────────────────────

class DocumentSummaryOut(BaseModel):
    total_pages: int = 1
    estimated_word_count: int = 0
    target_word_count: int = 1200
    transcription_status: str = "SUCCESS"
    has_handwritten_content: bool = True
    transcribed_text: str = ""


class ScoreSummaryOut(BaseModel):
    total_score: int
    max_score: int = 100
    grade: str = "D"
    performance_status: str = "Needs Work"


class AnnotationLocationOut(BaseModel):
    y_percent: float = 50.0
    position: str = "RIGHT_MARGIN"


class PageAnnotationOut(BaseModel):
    annotation_type: str
    target_snippet: str
    mark_symbol: str
    annotation_text: str
    location: AnnotationLocationOut
    page_number: int = 1


class ParameterBreakdownOut(BaseModel):
    parameter_name: str
    marks_obtained: int
    max_marks: int
    examiner_remark: str


class OverallEvaluationOut(BaseModel):
    summary_remarks: str = ""
    actionable_resubmission_checklist: list[str] = Field(default_factory=list)


# ── Legacy output types (kept for backward compat with standard/essay paths) ──

class ParameterScoreOut(BaseModel):
    parameter: RubricParameter
    score: int = Field(ge=0, le=10)
    max_score: int = 10
    justification: str
    suggestions: list[str] = Field(default_factory=list)


class EssayParameterScoreOut(BaseModel):
    parameter: str
    score: int = Field(ge=0)
    max_score: int
    examiner_remark: str
    suggestions: list[str] = Field(default_factory=list)


class AnnotationCommentOut(BaseModel):
    paragraph_index: int
    comment_text: str
    sentiment: str


# ── Top-level evaluation result ───────────────────────────────────────────────

class EvaluationResultOut(BaseModel):
    # Master-schema fields
    document_summary: DocumentSummaryOut = Field(
        default_factory=DocumentSummaryOut
    )
    score_summary: ScoreSummaryOut
    page_annotations: list[PageAnnotationOut] = Field(default_factory=list)
    parameter_breakdown: list[ParameterBreakdownOut] = Field(default_factory=list)
    overall_evaluation: OverallEvaluationOut = Field(
        default_factory=OverallEvaluationOut
    )

    # Legacy rubric fields (populated for non-handwritten fallback path)
    parameter_scores: list[ParameterScoreOut] = Field(default_factory=list)
    essay_parameter_scores: list[EssayParameterScoreOut] = Field(default_factory=list)
    before_resubmit: list[str] = Field(default_factory=list)

    # Shared
    exam_type: str = "Custom / General"
    strengths: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)


# ── Top-level API response ────────────────────────────────────────────────────

class EvaluateResponse(BaseModel):
    job_id: str
    original_file_url: str
    annotated_file_url: str     # URL to the checked PDF (or JPEG for legacy)
    report_url: str
    extracted_text: str         # full transcribed handwritten text
    word_count: int
    ocr_low_confidence: bool
    evaluation: EvaluationResultOut
    # Legacy flat list kept so existing frontend clients don't break
    annotation_comments: list[AnnotationCommentOut] = Field(default_factory=list)
