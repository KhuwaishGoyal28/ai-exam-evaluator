"""Unit tests for file_utils — pure functions."""
import pytest
from app.utils.file_utils import detect_file_type, validate_mime_type, validate_file_size
from app.core.constants import FileType
from app.core.exceptions import UnsupportedFileTypeError, FileTooLargeError


def test_detect_image_mime():
    assert detect_file_type("image/jpeg") == FileType.IMAGE
    assert detect_file_type("image/png") == FileType.IMAGE
    assert detect_file_type("image/webp") == FileType.IMAGE


def test_detect_pdf_mime():
    assert detect_file_type("application/pdf") == FileType.PDF


def test_detect_unsupported_mime():
    with pytest.raises(UnsupportedFileTypeError):
        detect_file_type("application/zip")


def test_validate_mime_type_passes():
    validate_mime_type("image/jpeg", ["image/jpeg", "application/pdf"])


def test_validate_mime_type_fails():
    with pytest.raises(UnsupportedFileTypeError):
        validate_mime_type("text/plain", ["image/jpeg"])


def test_validate_file_size_passes():
    validate_file_size(1024 * 1024, max_mb=5)  # 1MB < 5MB limit


def test_validate_file_size_fails():
    with pytest.raises(FileTooLargeError):
        validate_file_size(11 * 1024 * 1024, max_mb=10)  # 11MB > 10MB
