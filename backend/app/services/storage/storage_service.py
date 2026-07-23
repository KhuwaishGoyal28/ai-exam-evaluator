"""
Orchestrates cloud storage for one evaluation job.
Single responsibility: decide file paths + delegate to supabase_client.

Folder layout in Supabase bucket per job:
  evaluations/
    {job_id}/
      original.{ext}    ← raw upload, preserving original MIME type
      annotated.jpg     ← annotated image output
      report.json       ← complete evaluation report (JSON)

Using a per-job sub-folder makes it trivial to:
  - List all files for one evaluation
  - Delete a job (delete the whole folder)
  - Grant scoped access per user in the future
"""
from app.models.domain.answer import StoredFile
from app.core.logging import get_logger
from .supabase_client import upload_bytes, upload_json

logger = get_logger(__name__)

_MIME_TO_EXT: dict[str, str] = {
    "image/jpeg":      "jpg",
    "image/jpg":       "jpg",
    "image/png":       "png",
    "image/webp":      "webp",
    "application/pdf": "pdf",
}


def _job_folder(job_id: str) -> str:
    """Return the Supabase object path prefix for this job."""
    return f"evaluations/{job_id}"


def store_original_file(
    data: bytes,
    job_id: str,
    mime_type: str = "image/jpeg",
) -> StoredFile:
    """
    Upload the raw original file preserving its actual MIME type.
    Stored at:  evaluations/{job_id}/original.{ext}
    """
    ext = _MIME_TO_EXT.get(mime_type, "bin")
    path = f"{_job_folder(job_id)}/original.{ext}"
    logger.info("storing_original", job_id=job_id, mime=mime_type, path=path)
    return upload_bytes(data=data, object_path=path, content_type=mime_type)


def store_annotated_file(
    data: bytes,
    job_id: str,
    mime_type: str = "image/jpeg",
    extension: str = "jpg",
) -> StoredFile:
    """
    Upload the annotated output file.
    Primary path  → checked PDF  (mime_type=application/pdf, extension=pdf)
    Legacy path   → JPEG image   (mime_type=image/jpeg,      extension=jpg)

    Stored at:  evaluations/{job_id}/checked.{ext}
    """
    path = f"{_job_folder(job_id)}/checked.{extension}"
    logger.info("storing_annotated", job_id=job_id, mime=mime_type, path=path)
    return upload_bytes(data=data, object_path=path, content_type=mime_type)


def store_report(json_str: str, job_id: str) -> StoredFile:
    """
    Upload the full evaluation report as JSON.
    Stored at:  evaluations/{job_id}/report.json
    """
    path = f"{_job_folder(job_id)}/report.json"
    logger.info("storing_report", job_id=job_id, path=path)
    return upload_json(json_str=json_str, object_path=path)
