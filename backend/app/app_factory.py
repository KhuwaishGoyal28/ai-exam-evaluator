"""
FastAPI application factory.
Single responsibility: create and configure the FastAPI app instance.

Startup sequence:
  1. App object is created with default (empty) settings — always succeeds.
  2. On first request (lifespan), validate_secrets() is called.
     If secrets are missing, the server logs a clear actionable message and exits.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.api.v1.routes import api_router
from app.middleware.exception_handlers import EXCEPTION_HANDLERS

logger = get_logger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Validate required secrets on startup before accepting any requests."""
    settings = get_settings()
    try:
        settings.validate_secrets()
        logger.info("startup_ok", app=settings.app_name, version=settings.app_version)
    except RuntimeError as exc:
        # Print the full formatted message, then hard-exit so the process
        # doesn't silently serve 500s with missing credentials.
        import sys
        print(str(exc), file=sys.stderr)
        sys.exit(1)
    yield
    logger.info("shutdown")


def create_app() -> FastAPI:
    """Create, configure, and return the FastAPI application."""
    # Read settings for app metadata — secrets not validated yet.
    settings = get_settings()
    configure_logging(debug=settings.debug)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=_lifespan,
        docs_url="/docs",   # always available for local dev
        redoc_url="/redoc",
    )

    _register_cors(app, settings.allowed_origins)
    _register_routes(app)
    _register_exception_handlers(app)

    return app


def _register_cors(app: FastAPI, origins: list[str]) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def _register_routes(app: FastAPI) -> None:
    app.include_router(api_router, prefix="/api/v1")


def _register_exception_handlers(app: FastAPI) -> None:
    for exc_class, handler in EXCEPTION_HANDLERS:
        app.add_exception_handler(exc_class, handler)
