from fastapi import APIRouter
from .evaluate import router as evaluate_router
from .health import router as health_router

api_router = APIRouter(redirect_slashes=False)
api_router.include_router(health_router, tags=["Health"])
api_router.include_router(evaluate_router, tags=["Evaluation"])

__all__ = ["api_router"]
