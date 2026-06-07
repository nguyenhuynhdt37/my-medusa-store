from __future__ import annotations

import re
from typing import Any

import httpx

from app.core.config import settings
from app.core.exceptions import MedusaAPIError, MedusaTimeoutError


class MedusaClient:
    def __init__(
        self,
        base_url: str,
        publishable_api_key: str | None = None,
        region_id: str | None = None,
        region_country_code: str = "dk",
        timeout_seconds: float = 8.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.publishable_api_key = publishable_api_key
        self.region_id = region_id
        self.region_country_code = region_country_code.lower()
        self.timeout = httpx.Timeout(timeout_seconds)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
            ) as client:
                response = await client.request(
                    method,
                    path,
                    params=params,
                    headers=headers,
                )
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException as exc:
            raise MedusaTimeoutError("Medusa API request timed out") from exc
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            body = exc.response.text
            raise MedusaAPIError(
                f"Medusa API returned HTTP {status_code}: {body}",
                status_code=status_code,
            ) from exc
        except httpx.HTTPError as exc:
            raise MedusaAPIError(f"Medusa API request failed: {exc}") from exc

    async def list_products(self, query: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        headers = {}
        if self.publishable_api_key:
            headers["x-publishable-api-key"] = self.publishable_api_key

        params: dict[str, Any] = {"limit": limit}
        if query:
            params["q"] = query
        region_id = await self.get_region_id()
        if region_id:
            params["region_id"] = region_id

        data = await self._request("GET", "/store/products", params=params, headers=headers)
        return data.get("products", [])

    async def get_region_id(self) -> str | None:
        if self.region_id:
            return self.region_id

        headers = {}
        if self.publishable_api_key:
            headers["x-publishable-api-key"] = self.publishable_api_key

        data = await self._request("GET", "/store/regions", headers=headers)
        regions = data.get("regions", [])

        for region in regions:
            countries = region.get("countries", []) or []
            if any(str(country.get("iso_2", "")).lower() == self.region_country_code for country in countries):
                self.region_id = region.get("id")
                return self.region_id

        if regions:
            self.region_id = regions[0].get("id")
        return self.region_id

    async def find_order(self, order_code: str) -> dict[str, Any] | None:
        return await self.find_customer_order(order_code, customer_access_token=None)

    async def list_customer_orders(
        self,
        customer_access_token: str | None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        if not customer_access_token:
            raise MedusaAPIError("Customer access token is required for order lookup", status_code=401)

        headers = self._store_headers()
        headers["Authorization"] = format_bearer_token(customer_access_token)

        data = await self._request("GET", "/store/orders", params={"limit": limit}, headers=headers)
        return data.get("orders", [])

    async def find_customer_order(
        self,
        order_code: str,
        customer_access_token: str | None,
    ) -> dict[str, Any] | None:
        if not customer_access_token:
            raise MedusaAPIError("Customer access token is required for order lookup", status_code=401)

        headers = self._store_headers()
        headers["Authorization"] = format_bearer_token(customer_access_token)

        normalized = order_code.strip()
        display_id = self._extract_display_id(normalized)
        params: dict[str, Any] = {"limit": 100}
        if display_id is not None:
            params["display_id"] = display_id
        else:
            params["q"] = normalized

        data = await self._request("GET", "/store/orders", params=params, headers=headers)
        orders = data.get("orders", [])

        if display_id is not None:
            return next((order for order in orders if order.get("display_id") == display_id), None)

        normalized_lower = normalized.lower()
        return next(
            (
                order
                for order in orders
                if normalized_lower in str(order.get("id", "")).lower()
                or normalized_lower in str(order.get("display_id", "")).lower()
            ),
            None,
        )

    def _store_headers(self) -> dict[str, str]:
        headers = {}
        if self.publishable_api_key:
            headers["x-publishable-api-key"] = self.publishable_api_key
        return headers

    @staticmethod
    def _extract_display_id(order_code: str) -> int | None:
        match = re.search(r"(\d+)$", order_code)
        return int(match.group(1)) if match else None


def get_medusa_client() -> MedusaClient:
    return MedusaClient(
        base_url=settings.medusa_base_url,
        publishable_api_key=settings.medusa_publishable_api_key,
        region_id=settings.medusa_region_id,
        region_country_code=settings.medusa_region_country_code,
        timeout_seconds=settings.medusa_timeout_seconds,
    )


def format_bearer_token(token: str) -> str:
    token = token.strip()
    if token.lower().startswith("bearer "):
        return token
    return f"Bearer {token}"
