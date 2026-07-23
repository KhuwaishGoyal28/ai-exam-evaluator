"""
Application settings loaded once at startup via pydantic-settings.
All other modules import from here — never from os.environ directly.
"""
from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_FILE = _BACKEND_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── App ──────────────────────────────────────────────────────────────────
    app_name: str = "AnswerCheck API"
    app_version: str = "1.0.0"
    debug: bool = False
    allowed_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "https://ai-exam-evaluator-lilac.vercel.app/",
        "https://ai-exam-evaluator-chb7.onrender.com",
    ]

    # ── Groq (text evaluation + vision OCR) ──────────────────────────────────
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"        # text evaluation model
    groq_max_tokens: int = 1500
    groq_temperature: float = 0.2

    # Groq Vision — OCR for images and scanned PDFs
    groq_vision_model: str = "qwen/qwen3.6-27b"    # vision-capable model on Groq
    groq_vision_max_tokens: int = 1024              # keep output small to save TPM budget

    # ── OpenAI (optional — only used if groq_vision_model is unavailable) ────
    # Set OPENAI_API_KEY in .env to re-enable OpenAI as the OCR backend.
    openai_api_key: str = ""
    openai_vision_model: str = "gpt-4o-mini"
    openai_max_tokens: int = 8192

    # ── Supabase Storage ─────────────────────────────────────────────────────
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_bucket: str = "answercheck"

    # ── Upload constraints ────────────────────────────────────────────────────
    max_upload_size_mb: int = 10
    allowed_mime_types: list[str] = [
        "image/jpeg",
        "image/png",
        "image/webp",
        "application/pdf",
    ]

    # ── Rubric ───────────────────────────────────────────────────────────────
    rubric_max_score_per_param: int = 10

    def validate_secrets(self) -> None:
        """Validate required secrets at startup."""
        missing: list[str] = []
        placeholders = {"sk-...", "gsk_...", "your_key", ""}

        if not self.groq_api_key or self.groq_api_key in placeholders:
            missing.append("GROQ_API_KEY")
        # OpenAI key is now optional — Groq Vision handles OCR
        if not self.supabase_url or self.supabase_url in placeholders:
            missing.append("SUPABASE_URL")
        if not self.supabase_service_role_key or self.supabase_service_role_key in placeholders:
            missing.append("SUPABASE_SERVICE_ROLE_KEY")

        if missing:
            raise RuntimeError(
                f"\n\n{'='*60}\n"
                f"  AnswerCheck — missing required environment variables:\n\n"
                + "\n".join(f"    • {k}" for k in missing)
                + f"\n\n  Fill in the missing values in: {_ENV_FILE}\n"
                f"  Then restart uvicorn.\n"
                f"{'='*60}\n"
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
