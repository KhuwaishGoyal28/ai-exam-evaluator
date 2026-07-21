"""
Health check endpoint — used by deployment platforms to verify the service is up.
"""
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    version: str


@router.get("/health", response_model=HealthResponse, include_in_schema=False)
async def health_check() -> HealthResponse:
    from app.config import get_settings
    settings = get_settings()
    return HealthResponse(status="ok", version=settings.app_version)
