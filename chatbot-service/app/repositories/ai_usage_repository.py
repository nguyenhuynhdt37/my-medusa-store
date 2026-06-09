from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

import asyncpg


class AIUsageRepository:
    def __init__(self, pool_or_conn: asyncpg.Pool | asyncpg.Connection) -> None:
        self.db = pool_or_conn

    async def create_usage(self, **fields: Any) -> dict[str, Any]:
        row = await self._fetchrow(
            """
            INSERT INTO ai_usage (
              id, conversation_id, customer_id, guest_id, external_user_id, channel,
              provider, model, operation, intent, request_count, prompt_tokens,
              completion_tokens, total_tokens, estimated_cost_usd, unit_prices, metadata,
              duration_ms, memory_mb
            )
            VALUES (
              $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14,
              $15, $16::jsonb, $17::jsonb, $18, $19
            )
            RETURNING *
            """,
            fields.get("id") or f"aiu_{uuid4().hex}",
            fields.get("conversation_id"),
            fields.get("customer_id"),
            fields.get("guest_id"),
            fields.get("external_user_id"),
            fields.get("channel") or "WEB",
            fields["provider"],
            fields.get("model"),
            fields["operation"],
            fields.get("intent"),
            fields.get("request_count") or 1,
            fields.get("prompt_tokens"),
            fields.get("completion_tokens"),
            fields.get("total_tokens"),
            fields.get("estimated_cost_usd") or 0,
            _json(fields.get("unit_prices")),
            _json(fields.get("metadata")),
            fields.get("duration_ms"),
            fields.get("memory_mb"),
        )
        return _record(row)

    async def summary(self, *, start_at: str | None = None, end_at: str | None = None) -> dict[str, Any]:
        where, values = _date_filter(start_at, end_at)
        total = await self._fetchrow(
            f"""
            SELECT
              COALESCE(SUM(estimated_cost_usd), 0)::float8 AS total_cost_usd,
              COALESCE(SUM(request_count), 0)::int AS request_count,
              COALESCE(SUM(prompt_tokens), 0)::int AS prompt_tokens,
              COALESCE(SUM(completion_tokens), 0)::int AS completion_tokens,
              COALESCE(SUM(total_tokens), 0)::int AS total_tokens
            FROM ai_usage
            {where}
            """,
            *values,
        )
        return {
            "total": _record(total),
            "by_provider": await self._aggregate("provider", where, values),
            "by_channel": await self._aggregate("channel", where, values),
            "by_intent": await self._aggregate("intent", where, values),
            "top_customers": await self._top(
                "COALESCE(customer_id, guest_id, external_user_id, 'unknown')",
                "customer_key",
                where,
                values,
            ),
            "top_conversations": await self._top("conversation_id", "conversation_id", where, values),
        }

    async def analytics(
        self,
        *,
        start_at: str | None = None,
        end_at: str | None = None,
        trend_days: int = 30,
    ) -> dict[str, Any]:
        await self.refresh_daily_snapshot()
        where, values = _date_filter(start_at, end_at)
        return {
            "label": "Estimated AI Cost",
            "total": await self._estimated_total(where, values),
            "by_provider": await self._provider_breakdown(where, values),
            "by_channel": await self._breakdown_by_dimension("channel", "channel", where, values, limit=50),
            "by_intent": await self._breakdown_by_dimension("intent", "intent", where, values, limit=20),
            "top_conversations": await self._breakdown_by_dimension(
                "conversation_id",
                "conversation_id",
                where,
                values,
                limit=20,
                exclude_null=True,
            ),
            "top_customers": await self._breakdown_by_dimension(
                "COALESCE(customer_id, guest_id, external_user_id)",
                "customer_key",
                where,
                values,
                limit=20,
                exclude_null=True,
            ),
            "cost_by_day": await self.cost_by_day(days=trend_days),
            "trends": {
                "7d": await self.cost_by_day(days=7),
                "30d": await self.cost_by_day(days=30),
                "90d": await self.cost_by_day(days=90),
            },
            "monthly_projection": await self.monthly_projection(),
        }

    async def refresh_daily_snapshot(self, date: str | None = None) -> dict[str, Any]:
        date_expr = "$1::date" if date else "CURRENT_DATE"
        args = [date] if date else []
        row = await self._fetchrow(
            f"""
            INSERT INTO daily_ai_usage (
              date, lex_requests, gemini_prompt_tokens, gemini_completion_tokens,
              lambda_invocations, total_cost_usd, updated_at
            )
            SELECT
              {date_expr} AS date,
              COALESCE(SUM(request_count) FILTER (WHERE provider = 'LEX'), 0)::int AS lex_requests,
              COALESCE(SUM(prompt_tokens) FILTER (WHERE provider = 'GEMINI'), 0)::int AS gemini_prompt_tokens,
              COALESCE(SUM(completion_tokens) FILTER (WHERE provider = 'GEMINI'), 0)::int AS gemini_completion_tokens,
              COALESCE(SUM(request_count) FILTER (WHERE provider = 'LAMBDA'), 0)::int AS lambda_invocations,
              COALESCE(SUM(estimated_cost_usd), 0) AS total_cost_usd,
              now() AS updated_at
            FROM ai_usage
            WHERE created_at >= {date_expr}
              AND created_at < ({date_expr} + INTERVAL '1 day')
            ON CONFLICT (date)
            DO UPDATE SET
              lex_requests = EXCLUDED.lex_requests,
              gemini_prompt_tokens = EXCLUDED.gemini_prompt_tokens,
              gemini_completion_tokens = EXCLUDED.gemini_completion_tokens,
              lambda_invocations = EXCLUDED.lambda_invocations,
              total_cost_usd = EXCLUDED.total_cost_usd,
              updated_at = now()
            RETURNING *
            """,
            *args,
        )
        return _record(row)

    async def cost_by_day(self, *, days: int = 30) -> list[dict[str, Any]]:
        rows = await self._fetch(
            """
            SELECT
              day::date AS date,
              COALESCE(daily_ai_usage.total_cost_usd, 0)::float8 AS cost_usd,
              COALESCE(daily_ai_usage.lex_requests, 0)::int AS lex_requests,
              COALESCE(daily_ai_usage.gemini_prompt_tokens, 0)::int AS gemini_prompt_tokens,
              COALESCE(daily_ai_usage.gemini_completion_tokens, 0)::int AS gemini_completion_tokens,
              COALESCE(daily_ai_usage.lambda_invocations, 0)::int AS lambda_invocations
            FROM generate_series(
              CURRENT_DATE - (($1::int - 1) * INTERVAL '1 day'),
              CURRENT_DATE,
              INTERVAL '1 day'
            ) AS day
            LEFT JOIN daily_ai_usage ON daily_ai_usage.date = day::date
            ORDER BY day ASC
            """,
            days,
        )
        return [_record(row) for row in rows]

    async def monthly_projection(self) -> dict[str, Any]:
        row = await self._fetchrow(
            """
            WITH current_month AS (
              SELECT
                date_trunc('month', CURRENT_DATE)::date AS month_start,
                (date_trunc('month', CURRENT_DATE) + INTERVAL '1 month - 1 day')::date AS month_end
            ),
            totals AS (
              SELECT COALESCE(SUM(total_cost_usd), 0)::float8 AS cost_to_date
              FROM daily_ai_usage, current_month
              WHERE date >= month_start AND date <= CURRENT_DATE
            )
            SELECT
              current_month.month_start,
              current_month.month_end,
              EXTRACT(day FROM CURRENT_DATE)::int AS elapsed_days,
              EXTRACT(day FROM current_month.month_end)::int AS days_in_month,
              totals.cost_to_date,
              CASE
                WHEN EXTRACT(day FROM CURRENT_DATE)::int = 0 THEN 0
                ELSE (totals.cost_to_date / EXTRACT(day FROM CURRENT_DATE)::int)
                     * EXTRACT(day FROM current_month.month_end)::int
              END::float8 AS projected_cost_usd
            FROM current_month, totals
            """
        )
        data = _record(row)
        data["formula"] = "projected_cost_usd = cost_to_date / elapsed_days * days_in_month"
        data["label"] = "Estimated monthly AI cost projection"
        return data

    async def _aggregate(self, column: str, where: str, values: list[Any]) -> list[dict[str, Any]]:
        rows = await self._fetch(
            f"""
            SELECT
              COALESCE({column}, 'unknown') AS key,
              COALESCE(SUM(estimated_cost_usd), 0)::float8 AS total_cost_usd,
              COALESCE(SUM(request_count), 0)::int AS request_count,
              COALESCE(SUM(prompt_tokens), 0)::int AS prompt_tokens,
              COALESCE(SUM(completion_tokens), 0)::int AS completion_tokens,
              COALESCE(SUM(total_tokens), 0)::int AS total_tokens
            FROM ai_usage
            {where}
            GROUP BY key
            ORDER BY total_cost_usd DESC
            """,
            *values,
        )
        return [_record(row) for row in rows]

    async def _estimated_total(self, where: str, values: list[Any]) -> dict[str, Any]:
        row = await self._fetchrow(
            f"""
            SELECT
              COALESCE(SUM(estimated_cost_usd), 0)::float8 AS estimated_cost_usd,
              COALESCE(SUM(request_count), 0)::int AS request_count,
              COALESCE(SUM(request_count) FILTER (WHERE provider = 'LEX'), 0)::int AS lex_requests,
              COALESCE(SUM(request_count) FILTER (WHERE provider = 'LAMBDA'), 0)::int AS lambda_invocations,
              COALESCE(SUM(prompt_tokens) FILTER (WHERE provider = 'GEMINI'), 0)::int AS gemini_prompt_tokens,
              COALESCE(SUM(completion_tokens) FILTER (WHERE provider = 'GEMINI'), 0)::int AS gemini_completion_tokens,
              COALESCE(SUM(total_tokens) FILTER (WHERE provider = 'GEMINI'), 0)::int AS gemini_total_tokens
            FROM ai_usage
            {where}
            """,
            *values,
        )
        return _record(row)

    async def _provider_breakdown(self, where: str, values: list[Any]) -> list[dict[str, Any]]:
        rows = await self._fetch(
            f"""
            SELECT
              provider,
              COALESCE(SUM(estimated_cost_usd), 0)::float8 AS estimated_cost_usd,
              COALESCE(SUM(request_count), 0)::int AS request_count,
              COALESCE(SUM(prompt_tokens), 0)::int AS prompt_tokens,
              COALESCE(SUM(completion_tokens), 0)::int AS completion_tokens,
              COALESCE(SUM(total_tokens), 0)::int AS total_tokens,
              COALESCE(SUM(duration_ms), 0)::float8 AS duration_ms,
              MAX(memory_mb)::int AS memory_mb
            FROM ai_usage
            {where}
            GROUP BY provider
            ORDER BY estimated_cost_usd DESC
            """,
            *values,
        )
        return [_record(row) for row in rows]

    async def _breakdown_by_dimension(
        self,
        expression: str,
        alias: str,
        where: str,
        values: list[Any],
        *,
        limit: int,
        exclude_null: bool = False,
    ) -> list[dict[str, Any]]:
        dimension_filter = f"{expression} IS NOT NULL" if exclude_null else None
        filtered_where = _append_where(where, dimension_filter)
        rows = await self._fetch(
            f"""
            SELECT
              {expression} AS {alias},
              COALESCE(SUM(estimated_cost_usd), 0)::float8 AS estimated_cost_usd,
              COALESCE(SUM(request_count), 0)::int AS request_count,
              COALESCE(SUM(estimated_cost_usd) FILTER (WHERE provider = 'LEX'), 0)::float8 AS lex_cost_usd,
              COALESCE(SUM(estimated_cost_usd) FILTER (WHERE provider = 'GEMINI'), 0)::float8 AS gemini_cost_usd,
              COALESCE(SUM(estimated_cost_usd) FILTER (WHERE provider = 'LAMBDA'), 0)::float8 AS lambda_cost_usd,
              COALESCE(SUM(request_count) FILTER (WHERE provider = 'LEX'), 0)::int AS lex_requests,
              COALESCE(SUM(request_count) FILTER (WHERE provider = 'LAMBDA'), 0)::int AS lambda_invocations,
              COALESCE(SUM(prompt_tokens) FILTER (WHERE provider = 'GEMINI'), 0)::int AS gemini_prompt_tokens,
              COALESCE(SUM(completion_tokens) FILTER (WHERE provider = 'GEMINI'), 0)::int AS gemini_completion_tokens
            FROM ai_usage
            {filtered_where}
            GROUP BY {alias}
            ORDER BY estimated_cost_usd DESC
            LIMIT ${len(values) + 1}
            """,
            *values,
            limit,
        )
        return [_record(row) for row in rows]

    async def _top(self, expression: str, alias: str, where: str, values: list[Any]) -> list[dict[str, Any]]:
        rows = await self._fetch(
            f"""
            SELECT
              {expression} AS {alias},
              COALESCE(SUM(estimated_cost_usd), 0)::float8 AS total_cost_usd,
              COALESCE(SUM(request_count), 0)::int AS request_count,
              COALESCE(SUM(total_tokens), 0)::int AS total_tokens
            FROM ai_usage
            {where}
            GROUP BY {alias}
            ORDER BY total_cost_usd DESC
            LIMIT 10
            """,
            *values,
        )
        return [_record(row) for row in rows]

    async def _fetchrow(self, query: str, *args: Any) -> asyncpg.Record:
        if isinstance(self.db, asyncpg.Pool):
            async with self.db.acquire() as conn:
                return await conn.fetchrow(query, *args)
        return await self.db.fetchrow(query, *args)

    async def _fetch(self, query: str, *args: Any) -> list[asyncpg.Record]:
        if isinstance(self.db, asyncpg.Pool):
            async with self.db.acquire() as conn:
                return await conn.fetch(query, *args)
        return await self.db.fetch(query, *args)


def _date_filter(start_at: str | None, end_at: str | None) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    values: list[Any] = []
    if start_at:
        values.append(start_at)
        clauses.append(f"created_at >= ${len(values)}::timestamptz")
    if end_at:
        values.append(end_at)
        clauses.append(f"created_at < ${len(values)}::timestamptz")
    return (f"WHERE {' AND '.join(clauses)}" if clauses else "", values)


def _append_where(where: str, clause: str | None) -> str:
    if not clause:
        return where
    if where:
        return f"{where} AND {clause}"
    return f"WHERE {clause}"


def _json(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, default=str)


def _record(row: asyncpg.Record) -> dict[str, Any]:
    data = dict(row)
    for key, value in list(data.items()):
        if key.endswith("_at") and value is not None:
            data[key] = value.isoformat()
        if key in {"unit_prices", "metadata"} and isinstance(value, str):
            data[key] = json.loads(value)
    return data
