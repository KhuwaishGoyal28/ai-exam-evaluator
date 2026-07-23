"""
/api/v1/evaluate — accepts POST with or without trailing slash.
No 308 redirects possible: redirect_slashes=False on every layer
AND both paths registered explicitly.
"""
from fastapi import APIRouter, UploadFile, File, Form, status, Response
from app.models.domain.answer import UploadedFile
from app.models.responses.evaluate import EvaluateResponse
from app.api.v1.controllers import process_answer_submission
from app.utils.file_utils import detect_file_type, validate_mime_type, validate_file_size
from app.core.constants import ExamType
from app.config import get_settings
from app.core.logging import get_logger

# Disable automatic redirect slashes on the router level
router = APIRouter(redirect_slashes=False)
logger = get_logger(__name__)


async def _run_pipeline(
    file: UploadFile,
    question: str | None,
    exam_type: str,
) -> EvaluateResponse:
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


# Primary route (without slash)
@router.post(
    "/evaluate",
    response_model=EvaluateResponse,
    status_code=status.HTTP_200_OK,
)
# Secondary route (with slash) — hidden from OpenAPI/Swagger schema to avoid duplicate docs
@router.post(
    "/evaluate/",
    response_model=EvaluateResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def evaluate_answer(
    response: Response,
    file: UploadFile = File(...),
    question: str | None = Form(default=None),
    exam_type: str = Form(default="Custom / General"),
) -> EvaluateResponse:
    # Tell proxies/CDNs not to cache this endpoint and not to time it out early
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Accel-Buffering"] = "no"   # Nginx: disable buffering
    return await _run_pipeline(file, question, exam_type)