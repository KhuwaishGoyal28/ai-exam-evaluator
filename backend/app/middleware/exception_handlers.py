"""
Global FastAPI exception handlers.
Maps domain exceptions to HTTP status codes + ErrorResponse JSON.
Single responsibility: exception type → HTTP response.
"""
from fastapi import Request, status
from fastapi.responses import JSONResponse
from app.core.exceptions import (
    UnsupportedFileTypeError,
    FileTooLargeError,
    OCRExtractionError,
    LowOCRConfidenceError,
    EvaluationError,
    AnnotationError,
    StorageError,
    ExternalServiceError,
    AnswerCheckError,
)
from app.models.responses.error import ErrorResponse, ErrorDetail
from app.core.logging import get_logger

logger = get_logger(__name__)


def _make_error_response(code: str, message: str, status_code: int) -> JSONResponse:
    body = ErrorResponse(error=ErrorDetail(code=code, message=message))
    return JSONResponse(status_code=status_code, content=body.model_dump())


async def handle_unsupported_file_type(
    request: Request, exc: UnsupportedFileTypeError
) -> JSONResponse:
    return _make_error_response("UNSUPPORTED_FILE_TYPE", str(exc), status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)


async def handle_file_too_large(
    request: Request, exc: FileTooLargeError
) -> JSONResponse:
    return _make_error_response("FILE_TOO_LARGE", str(exc), status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)


async def handle_ocr_error(
    request: Request, exc: OCRExtractionError
) -> JSONResponse:
    logger.warning("ocr_error", error=str(exc))
    return _make_error_response("OCR_FAILED", str(exc), status.HTTP_422_UNPROCESSABLE_ENTITY)


async def handle_low_confidence(
    request: Request, exc: LowOCRConfidenceError
) -> JSONResponse:
    return _make_error_response(
        "LOW_OCR_CONFIDENCE",
        "Image quality is too low to extract text reliably. Please upload a clearer scan.",
        status.HTTP_422_UNPROCESSABLE_ENTITY,
    )


async def handle_evaluation_error(
    request: Request, exc: EvaluationError
) -> JSONResponse:
    logger.error("evaluation_error", error=str(exc))
    return _make_error_response("EVALUATION_FAILED", str(exc), status.HTTP_502_BAD_GATEWAY)


async def handle_annotation_error(
    request: Request, exc: AnnotationError
) -> JSONResponse:
    logger.error("annotation_error", error=str(exc))
    return _make_error_response("ANNOTATION_FAILED", str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


async def handle_storage_error(
    request: Request, exc: StorageError
) -> JSONResponse:
    logger.error("storage_error", error=str(exc))
    return _make_error_response("STORAGE_FAILED", str(exc), status.HTTP_502_BAD_GATEWAY)


async def handle_external_service_error(
    request: Request, exc: ExternalServiceError
) -> JSONResponse:
    logger.error("external_service_error", error=str(exc))
    return _make_error_response(
        "EXTERNAL_SERVICE_ERROR",
        "An upstream service is unavailable. Please try again.",
        status.HTTP_502_BAD_GATEWAY,
    )


async def handle_generic_error(
    request: Request, exc: Exception
) -> JSONResponse:
    logger.error("unhandled_error", error=str(exc), path=str(request.url))
    return _make_error_response(
        "INTERNAL_ERROR",
        "An unexpected error occurred. Please try again.",
        status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


# Registry used by the app factory
EXCEPTION_HANDLERS: list[tuple] = [
    (UnsupportedFileTypeError, handle_unsupported_file_type),
    (FileTooLargeError, handle_file_too_large),
    (LowOCRConfidenceError, handle_low_confidence),
    (OCRExtractionError, handle_ocr_error),
    (EvaluationError, handle_evaluation_error),
    (AnnotationError, handle_annotation_error),
    (StorageError, handle_storage_error),
    (ExternalServiceError, handle_external_service_error),
    (Exception, handle_generic_error),
]
