from fastapi import FastAPI

from app.api.webhook import router as webhook_router
from app.api.websocket import router as websocket_router
from app.core.config import settings


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)
    app.include_router(webhook_router)
    app.include_router(websocket_router)
    return app


app = create_app()

