from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response
import httpx

from app.core.config import settings

router = APIRouter(tags=["storefront-proxy"])

HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "content-encoding",
}


@router.api_route(
    "/{path:path}",
    methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
)
async def proxy_storefront(path: str, request: Request) -> Response:
    target = f"{settings.storefront_internal_url.rstrip('/')}/{path}"
    if request.url.query:
        target = f"{target}?{request.url.query}"

    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in HOP_BY_HOP_HEADERS and key.lower() != "host"
    }

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(20.0), follow_redirects=False) as client:
            upstream = await client.request(
                request.method,
                target,
                headers=headers,
                content=await request.body(),
            )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail="Storefront service is unavailable",
        ) from exc

    response_headers = {
        key: value
        for key, value in upstream.headers.items()
        if key.lower() not in HOP_BY_HOP_HEADERS
    }
    return Response(
        content=upstream.content if request.method != "HEAD" else b"",
        status_code=upstream.status_code,
        headers=response_headers,
        media_type=upstream.headers.get("content-type"),
    )
