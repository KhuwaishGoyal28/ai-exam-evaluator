"""
Pydantic response schemas for the /evaluate endpoint.
Matches the teacher-evaluation JSON schema from the Vision agent.
"""
from __future__ import annotations
from pydantic import BaseModel, Field
from app.core.constants import RubricParameter


# ── Primary: teacher-evaluation schema ───────────────────────────────────────

class RubricItemOut(BaseModel):
    marks: int
    max: int
    remark: str = ""


class TeacherAnnotationOut(BaseModel):
    page: int
    paragraph: int
    sentence: int | None = None
    annotation_type: str         # tick | cross | circle | underline | comment
    comment: str


class EvaluationSummaryOut(BaseModel):
    student_name: str = ""
    subject: str = ""
    has_handwritten_content: bool = True
    transcribed_text: str = ""
    total_marks: int
    max_marks: int = 100
    grade: str = "D"
    performance_level: str = "Needs Improvement"
    rubric: dict[str, RubricItemOut] = Field(default_factory=dict)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    remarks: str = ""
    annotations: list[TeacherAnnotationOut] = Field(default_factory=list)
    total_pages: int = 1


# ── Legacy schema types (kept for backward compat) ────────────────────────────

class ScoreSummaryOut(BaseModel):
    total_score: int
    max_score: int = 100
    grade: str = "D"
    performance_status: str = "Needs Work"


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


# ── Top-level response ────────────────────────────────────────────────────────

class EvaluateResponse(BaseModel):
    job_id: str
    original_file_url: str
    annotated_file_url: str      # URL to the checked PDF
    report_url: str
    extracted_text: str          # full transcribed handwritten text
    word_count: int
    ocr_low_confidence: bool

    # Primary evaluation result (always populated for handwritten uploads)
    evaluation_summary: EvaluationSummaryOut

    # Legacy annotation comments (kept for frontend compat)
    annotation_comments: list[AnnotationCommentOut] = Field(default_factory=list)

    # Legacy flat score fields (kept for frontend compat)
    total_marks: int = 0
    max_marks: int = 100
    grade: str = "D"
    performance_level: str = "Needs Improvement"
