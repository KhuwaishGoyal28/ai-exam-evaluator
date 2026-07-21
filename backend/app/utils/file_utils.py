"""
Pure utility functions for file validation and type detection.
No I/O, no external calls — safe to unit-test in isolation.
"""
import mimetypes
from app.core.constants import FileType
from app.core.exceptions import UnsupportedFileTypeError, FileTooLargeError


def detect_file_type(mime_type: str) -> FileType:
    """Map a MIME type string to a FileType enum value."""
    if mime_type.startswith("image/"):
        return FileType.IMAGE
    if mime_type == "application/pdf":
        return FileType.PDF
    raise UnsupportedFileTypeError(
        f"MIME type '{mime_type}' is not supported. "
        "Upload a JPEG, PNG, WebP image or a PDF."
    )


def validate_mime_type(mime_type: str, allowed: list[str]) -> None:
    """Raise UnsupportedFileTypeError if mime_type not in allowed list."""
    if mime_type not in allowed:
        raise UnsupportedFileTypeError(
            f"File type '{mime_type}' is not allowed. "
            f"Accepted types: {', '.join(allowed)}"
        )


def validate_file_size(size_bytes: int, max_mb: int) -> None:
    """Raise FileTooLargeError if file exceeds the byte limit."""
    max_bytes = max_mb * 1024 * 1024
    if size_bytes > max_bytes:
        raise FileTooLargeError(
            f"File size {size_bytes / 1024 / 1024:.1f} MB exceeds "
            f"the {max_mb} MB limit."
        )


def guess_extension(mime_type: str) -> str:
    """Return a file extension (with dot) for the given MIME type."""
    ext = mimetypes.guess_extension(mime_type)
    overrides = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "application/pdf": ".pdf",
    }
    return overrides.get(mime_type, ext or ".bin")
