from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.admin_ai_usage import router as admin_ai_usage_router
from app.api.admin_conversations import router as admin_conversations_router
from app.api.facebook import router as facebook_router
from app.api.webhook import router as webhook_router
from app.api.chat_gateway import router as chat_gateway_router
from app.api.websocket import router as websocket_router
from app.api.storefront_proxy import router as storefront_proxy_router
from app.core.database import close_pool, run_migrations
from app.core.config import settings
from app.services.ai_usage_snapshot_job import ai_usage_snapshot_job


@asynccontextmanager
async def lifespan(app: FastAPI):
    await run_migrations()
    ai_usage_snapshot_job.start()
    try:
        yield
    finally:
        await ai_usage_snapshot_job.stop()
        await close_pool()


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.include_router(webhook_router)
    app.include_router(chat_gateway_router)
    app.include_router(facebook_router)
    app.include_router(admin_ai_usage_router)
    app.include_router(admin_conversations_router)
    app.include_router(websocket_router)
    
    @app.get("/health", tags=["Health"])
    async def health_check():
        return {"status": "ok"}
        
    app.include_router(storefront_proxy_router)
    return app


app = create_app()
