"""
Application entrypoint.
Intentionally minimal — all setup lives in app_factory.py.
"""
import uvicorn
from app.app_factory import create_app

app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
