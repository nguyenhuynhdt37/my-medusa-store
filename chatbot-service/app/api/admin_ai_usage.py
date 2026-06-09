from __future__ import annotations

from fastapi import APIRouter, Query

from app.core.database import get_pool
from app.repositories.ai_usage_repository import AIUsageRepository

router = APIRouter(prefix="/admin/ai-usage", tags=["admin-ai-usage"])


@router.get("/summary")
async def ai_usage_summary(
    start_at: str | None = Query(default=None),
    end_at: str | None = Query(default=None),
    trend_days: int = Query(default=30, ge=1, le=365),
):
    repository = AIUsageRepository(await get_pool())
    return await repository.analytics(start_at=start_at, end_at=end_at, trend_days=trend_days)


@router.post("/daily-snapshots/refresh")
async def refresh_daily_ai_usage_snapshot(
    date: str | None = Query(default=None),
):
    repository = AIUsageRepository(await get_pool())
    return await repository.refresh_daily_snapshot(date=date)


@router.get("/trends")
async def ai_usage_trends(
    days: int = Query(default=30, ge=1, le=365),
):
    repository = AIUsageRepository(await get_pool())
    return {
        "label": "Estimated AI Cost",
        "cost_by_day": await repository.cost_by_day(days=days),
    }


@router.get("/projection")
async def ai_usage_monthly_projection():
    repository = AIUsageRepository(await get_pool())
    return await repository.monthly_projection()
