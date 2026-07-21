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

router = APIRouter(redirect_slashes=False)
logger = get_logger(__name__)

async def _handle_evaluate(
    file: UploadFile,
    question: str | None,
    exam_type: str,
) -> EvaluateResponse:
    """Shared handler used by both /evaluate and /evaluate/ routes."""
    settings = get_settings()
    raw_bytes = await file.read()

    validate_mime_type(file.content_type, settings.allowed_mime_types)
    validate_file_size(len(raw_bytes), settings.max_upload_size_mb)
    file_type = detect_file_type(file.content_type)

    try:
        exam_type_enum = ExamType(exam_type)
    except ValueError:
        exam_type_enum = ExamType.CUSTOM

    uploaded_file = UploadedFile(
        filename=file.filename or "upload",
        mime_type=file.content_type,
        file_type=file_type,
        content=raw_bytes,
        size_bytes=len(raw_bytes),
    )

    return await process_answer_submission(uploaded_file, question, exam_type_enum)


# Register both with AND without trailing slash — eliminates all 308 redirects
@router.post("/evaluate", response_model=EvaluateResponse, status_code=status.HTTP_200_OK)
@router.post("/evaluate/", response_model=EvaluateResponse, status_code=status.HTTP_200_OK, include_in_schema=False)
async def evaluate_answer(
    file: UploadFile = File(...),
    question: str | None = Form(default=None),
    exam_type: str = Form(default="Custom / General"),
) -> EvaluateResponse:
    return await _handle_evaluate(file, question, exam_type)
