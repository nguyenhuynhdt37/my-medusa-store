from __future__ import annotations

import asyncio
from datetime import date, timedelta

from app.core.config import settings
from app.core.database import get_pool
from app.repositories.ai_usage_repository import AIUsageRepository


class AIUsageSnapshotJob:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    def start(self) -> None:
        if self._task or not settings.ai_usage_snapshot_job_enabled or not settings.database_url:
            return
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if not self._task:
            return
        self._stop.set()
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def _run(self) -> None:
        while not self._stop.is_set():
            await refresh_recent_daily_ai_usage_snapshots()
            try:
                await asyncio.wait_for(
                    self._stop.wait(),
                    timeout=settings.ai_usage_snapshot_interval_seconds,
                )
            except asyncio.TimeoutError:
                continue


async def refresh_recent_daily_ai_usage_snapshots() -> None:
    repository = AIUsageRepository(await get_pool())
    today = date.today()
    for day in (today - timedelta(days=1), today):
        try:
            await repository.refresh_daily_snapshot(date=day.isoformat())
        except Exception as exc:
            print("[AI_USAGE_SNAPSHOT_FAILED]", {"date": day.isoformat(), "error": str(exc)}, flush=True)


ai_usage_snapshot_job = AIUsageSnapshotJob()
