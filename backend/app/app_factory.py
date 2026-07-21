"""
FastAPI application factory.
Serves both the REST API (/api/v1/*) and the React SPA (/*) from one process.
The React build is copied to backend/static/ during the Render build step.
"""
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.api.v1.routes import api_router
from app.middleware.exception_handlers import EXCEPTION_HANDLERS

logger = get_logger(__name__)

# Path to the React build output (copied here during build.sh)
_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


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
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
    )

    _register_cors(app, settings.allowed_origins)
    _register_api_routes(app)
    _register_static_frontend(app)
    _register_exception_handlers(app)

    return app


def _register_cors(app: FastAPI, origins: list[str]) -> None:
    """CORS only needed if frontend and backend are on different domains."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def _register_api_routes(app: FastAPI) -> None:
    app.include_router(api_router, prefix="/api/v1")


def _register_static_frontend(app: FastAPI) -> None:
    """
    Serve the React SPA from backend/static/.

    Routing priority (FastAPI matches top-to-bottom):
      1. /api/v1/* → handled by the API router (registered first)
      2. /assets/* → StaticFiles mount (JS, CSS, images with hashed names)
      3. /*         → index.html catch-all for React Router (GET only,
                       and explicitly skips /api/ paths so POSTs are never blocked)

    If static/ doesn't exist (local dev) this is a no-op — Vite handles the frontend.
    """
    if not _STATIC_DIR.exists():
        logger.info(
            "static_dir_missing",
            path=str(_STATIC_DIR),
            note="frontend served by Vite in dev",
        )
        return

    # Serve hashed /assets/* files (JS bundles, CSS, images)
    assets_dir = _STATIC_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    # Serve other static root files (favicon, robots.txt, etc.)
    index_html = _STATIC_DIR / "index.html"

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str) -> FileResponse:
        """
        SPA catch-all — returns index.html for every non-API GET request
        so React Router can handle client-side navigation.

        Explicitly passes through /api/ paths so this handler never
        intercepts API calls (which would cause 405 on POST requests).
        """
        # Let /api/* routes fall through to the actual API router
        if full_path.startswith("api/"):
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="API route not found")
        return FileResponse(str(index_html))

    logger.info("static_frontend_mounted", path=str(_STATIC_DIR))


def _register_exception_handlers(app: FastAPI) -> None:
    for exc_class, handler in EXCEPTION_HANDLERS:
        app.add_exception_handler(exc_class, handler)
