from fastapi import FastAPI

from app.api.facebook import router as facebook_router
from app.api.webhook import router as webhook_router
from app.api.chat_gateway import router as chat_gateway_router
from app.api.websocket import router as websocket_router
from app.api.storefront_proxy import router as storefront_proxy_router
from app.core.config import settings


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)
    app.include_router(webhook_router)
    app.include_router(chat_gateway_router)
    app.include_router(facebook_router)
    app.include_router(websocket_router)
    app.include_router(storefront_proxy_router)
    return app


app = create_app()
