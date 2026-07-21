"""
/api/v1/evaluate route.
Single responsibility: parse HTTP, delegate to controller, return HTTP response.
"""
from fastapi import APIRouter, UploadFile, File, Form, status
from app.models.domain.answer import UploadedFile
from app.models.responses.evaluate import EvaluateResponse
from app.api.v1.controllers import process_answer_submission
from app.utils.file_utils import detect_file_type, validate_mime_type, validate_file_size
from app.core.constants import ExamType
from app.config import get_settings
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.post(
    "/evaluate",
    response_model=EvaluateResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit an answer sheet for OCR + AI evaluation",
    description="Upload a JPEG/PNG/WebP image or PDF. Returns OCR text, rubric scores, annotated image.",
)
async def evaluate_answer(
    file: UploadFile = File(..., description="Image (JPEG/PNG/WebP) or PDF of the answer"),
    question: str | None = Form(default=None, description="Exam question or topic"),
    exam_type: str = Form(default="UPSC Mains", description="Exam type for rubric context"),
) -> EvaluateResponse:
    settings = get_settings()
    raw_bytes = await file.read()

    validate_mime_type(file.content_type, settings.allowed_mime_types)
    validate_file_size(len(raw_bytes), settings.max_upload_size_mb)
    file_type = detect_file_type(file.content_type)

    try:
        exam_type_enum = ExamType(exam_type)
    except ValueError:
        exam_type_enum = ExamType.UPSC

    uploaded_file = UploadedFile(
        filename=file.filename or "upload",
        mime_type=file.content_type,
        file_type=file_type,
        content=raw_bytes,
        size_bytes=len(raw_bytes),
    )

    return await process_answer_submission(uploaded_file, question, exam_type_enum)
