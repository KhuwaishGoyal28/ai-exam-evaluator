"""
Pydantic response schemas for the /evaluate endpoint.
Decoupled from domain models.

Supports both rubric modes:
  Standard  — parameter_scores populated, essay_parameter_scores empty
  Essay     — essay_parameter_scores populated, parameter_scores empty
"""
from pydantic import BaseModel, Field
from app.core.constants import RubricParameter


class ParameterScoreOut(BaseModel):
    """One row in the standard 5-parameter rubric table."""
    parameter: RubricParameter
    score: int = Field(ge=0, le=10)
    max_score: int = 10
    justification: str
    suggestions: list[str] = Field(default_factory=list)


class EssayParameterScoreOut(BaseModel):
    """One row in the 12-parameter essay rubric table."""
    parameter: str          # EssayRubricParameter.value
    score: int = Field(ge=0)
    max_score: int          # per-parameter maximum (varies)
    examiner_remark: str    # crisp one-line remark as on the evaluation sheet
    suggestions: list[str] = Field(default_factory=list)


class AnnotationCommentOut(BaseModel):
    paragraph_index: int
    comment_text: str
    sentiment: str


class EvaluationResultOut(BaseModel):
    # Standard rubric (non-essay)
    parameter_scores: list[ParameterScoreOut] = Field(default_factory=list)

    # Essay rubric
    essay_parameter_scores: list[EssayParameterScoreOut] = Field(default_factory=list)
    before_resubmit: list[str] = Field(default_factory=list)

    # Shared
    total_score: int
    max_total_score: int = 50
    overall_remark: str
    exam_type: str = "Custom / General"
    strengths: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)

    @property
    def is_essay(self) -> bool:
        return bool(self.essay_parameter_scores)


class EvaluateResponse(BaseModel):
    job_id: str
    original_file_url: str
    annotated_file_url: str
    report_url: str
    extracted_text: str
    word_count: int
    ocr_low_confidence: bool
    evaluation: EvaluationResultOut
    annotation_comments: list[AnnotationCommentOut]
