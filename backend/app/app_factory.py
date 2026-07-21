"""
FastAPI application factory.
Backend API only — frontend is served separately on Vercel.
CORS allows the Vercel frontend domain.
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
    settings = get_settings()
    try:
        settings.validate_secrets()
        logger.info("startup_ok", app=settings.app_name, version=settings.app_version)
    except RuntimeError as exc:
        import sys
        print(str(exc), file=sys.stderr)
        sys.exit(1)
    yield
    logger.info("shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(debug=settings.debug)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=_lifespan,
        redirect_slashes=False,          # ← prevents ALL 308 redirects
        docs_url="/docs",
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
