"""
Supabase Storage upload helpers.
Single responsibility: bytes/text + path → StoredFile.

All files for one evaluation live under:
  evaluations/{job_id}/
    original.{ext}    ← raw upload
    annotated.jpg     ← annotated output
    report.json       ← full evaluation report

Uses the Supabase Storage REST API directly via httpx
(no supabase-py needed — lighter dependency).
"""
from __future__ import annotations

import httpx

from app.config import get_settings
from app.models.domain.answer import StoredFile
from app.core.exceptions import StorageError
from app.core.logging import get_logger

logger = get_logger(__name__)


# ── private helpers ────────────────────────────────────────────────────────


def _base_url() -> str:
    return f"{get_settings().supabase_url.rstrip('/')}/storage/v1"


def _headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    key = get_settings().supabase_service_role_key
    h = {
        "Authorization": f"Bearer {key}",
        "apikey": key,
        "x-upsert": "true",
    }
    if extra:
        h.update(extra)
    return h


def _public_url(bucket: str, object_path: str) -> str:
    base = get_settings().supabase_url.rstrip("/")
    return f"{base}/storage/v1/object/public/{bucket}/{object_path}"


def _check_response(response: httpx.Response, path: str) -> None:
    """Raise StorageError on non-2xx with a clear message."""
    if response.is_success:
        return
    try:
        detail = response.json()
    except Exception:
        detail = response.text
    raise StorageError(
        f"Supabase Storage {response.status_code} for '{path}': {detail}"
    )


# ── public API ─────────────────────────────────────────────────────────────


def upload_bytes(
    data: bytes,
    object_path: str,
    content_type: str = "image/jpeg",
) -> StoredFile:
    """
    Upload raw bytes to Supabase Storage.
    Returns a StoredFile with the public URL.
    """
    settings = get_settings()
    bucket = settings.supabase_bucket
    url = f"{_base_url()}/object/{bucket}/{object_path}"

    try:
        resp = httpx.put(
            url,
            content=data,
            headers=_headers({"Content-Type": content_type}),
            timeout=60,
        )
        _check_response(resp, object_path)
    except StorageError:
        raise
    except Exception as exc:
        logger.error("supabase_upload_failed", path=object_path, error=str(exc))
        raise StorageError(f"Supabase upload failed for '{object_path}': {exc}") from exc

    pub = _public_url(bucket, object_path)
    logger.info("supabase_upload_ok", path=object_path, url=pub)

    return StoredFile(
        public_id=object_path,
        url=pub,
        secure_url=pub,
        resource_type="raw" if object_path.endswith(".json") else "image",
        format=object_path.rsplit(".", 1)[-1] if "." in object_path else "bin",
    )


def upload_json(json_str: str, object_path: str) -> StoredFile:
    """
    Upload a JSON string as application/json.
    Thin wrapper around upload_bytes.
    """
    return upload_bytes(
        data=json_str.encode("utf-8"),
        object_path=object_path,
        content_type="application/json",
    )
