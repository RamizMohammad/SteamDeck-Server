"""Request helpers shared by the REST routes."""

from __future__ import annotations

import json
from typing import Any

from fastapi import Request

from . import security


class ApiError(Exception):
    """Raised anywhere in a route; rendered as {"error": message} like the old server."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


async def read_json(request: Request) -> dict[str, Any]:
    """Parse the body the way `express.json()` + destructuring effectively behaved.

    Non-object bodies yield {} so the route's own "X is required" 400 fires
    (the old server crashed with a 500 in that case).
    """
    max_bytes: int = request.app.state.settings.max_body_bytes
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > max_bytes:
        raise ApiError(413, "Request body too large")

    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > max_bytes:
            raise ApiError(413, "Request body too large")

    if not body.strip():
        return {}
    try:
        data = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        raise ApiError(400, "Invalid JSON body") from None
    return data if isinstance(data, dict) else {}


def require_user(request: Request) -> str:
    """FastAPI dependency equivalent to the old authMiddleware. Returns the userId (ObjectId hex)."""
    user_id, err = security.user_id_from_header(request.headers.get("authorization"))
    if err or user_id is None:
        raise ApiError(401, err or "Unauthorized: Invalid token")
    return user_id


def client_ip(request: Request) -> str:
    """The address our nginx saw: the LAST X-Forwarded-For entry (nginx appends it).
    Earlier entries are client-supplied and can't be trusted for rate limiting."""
    hops: int = request.app.state.settings.trusted_proxy_hops
    xff = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",") if p.strip()]
    if hops > 0 and xff:
        return xff[-hops] if len(xff) >= hops else xff[0]
    return request.client.host if request.client else "unknown"


def without_password(user: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in user.items() if k != "passwordHash"}
