"""
Pydantic response schemas for the /evaluate endpoint.
Decoupled from domain models.
"""
from pydantic import BaseModel, Field
from app.core.constants import RubricParameter


class ParameterScoreOut(BaseModel):
    parameter: RubricParameter
    score: int = Field(ge=0, le=10)
    max_score: int = 10
    justification: str
    suggestions: list[str] = Field(default_factory=list)


class AnnotationCommentOut(BaseModel):
    paragraph_index: int
    comment_text: str
    sentiment: str


class EvaluationResultOut(BaseModel):
    parameter_scores: list[ParameterScoreOut]
    total_score: int
    max_total_score: int = 50
    overall_remark: str
    exam_type: str = "UPSC Mains"
    strengths: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)


class EvaluateResponse(BaseModel):
    job_id: str
    original_file_url: str
    annotated_file_url: str
    report_url: str          # full evaluation JSON stored in cloud
    extracted_text: str
    word_count: int
    ocr_low_confidence: bool
    evaluation: EvaluationResultOut
    annotation_comments: list[AnnotationCommentOut]
