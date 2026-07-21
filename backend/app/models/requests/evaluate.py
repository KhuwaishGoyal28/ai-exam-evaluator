"""
Pydantic schema for the /evaluate endpoint request.
"""
from pydantic import BaseModel, Field
from app.core.constants import ExamType


class EvaluateRequest(BaseModel):
    question: str | None = Field(
        default=None,
        max_length=1000,
        description="The exam question or topic the answer addresses (optional).",
    )
    exam_type: ExamType = Field(
        default=ExamType.UPSC,
        description="Exam category — determines rubric context and scoring standards.",
    )
