"""POST /api/auth (login-or-signup) and GET /api/me."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request

from .. import security, store
from ..http import ApiError, client_ip, read_json, require_user, without_password
from ..jscompat import JSResponse, now_ms, truthy
from ..ratelimit import SlidingWindow

log = logging.getLogger("linkium.auth")
router = APIRouter()

_ip_limiter: SlidingWindow | None = None
_fail_limiter: SlidingWindow | None = None

TOO_MANY = "Too many attempts. Please try again later."


def _limiters(request: Request) -> tuple[SlidingWindow, SlidingWindow]:
    global _ip_limiter, _fail_limiter
    if _ip_limiter is None or _fail_limiter is None:
        cfg = request.app.state.settings
        _ip_limiter = SlidingWindow(cfg.auth_rate_per_minute, 60)
        _fail_limiter = SlidingWindow(cfg.auth_fail_per_15min, 15 * 60)
    return _ip_limiter, _fail_limiter


@router.post("/auth")
async def auth(request: Request):
    body = await read_json(request)
    email, password = body.get("email"), body.get("password")

    if not truthy(email) or not truthy(password):
        raise ApiError(400, "Email and password are required")
    if not isinstance(email, str) or not isinstance(password, str):
        raise ApiError(400, "Email and password are required")

    ip_limiter, fail_limiter = _limiters(request)
    ip = client_ip(request)
    if ip_limiter.blocked(ip) or fail_limiter.blocked(email):
        raise ApiError(429, TOO_MANY)
    ip_limiter.hit(ip)

    for _attempt in range(2):  # second pass only after losing a signup race
        existing = await store.find_user_by_email(email)

        if existing:
            if not await security.verify_password(password, existing.get("passwordHash")):
                fail_limiter.hit(email)
                raise ApiError(401, "Wrong password")
            fail_limiter.reset(email)
            token = security.generate_token(existing["_id"])
            return JSResponse({"token": token, "user": without_password(existing)})

        created_at = now_ms()
        first = {"ts": now_ms(), "type": "info", "msg": "Account created", "raw": {}}
        try:
            user_id = await store.create_user(email, await security.hash_password(password), first, created_at)
        except store.Conflict:
            continue

        # Same shape and key order the old server returned for a new account
        user_out = {
            "email": email,
            "programsFetched": False,
            "programs": [],
            "activityLog": [first],
            "createdAt": created_at,
            "_id": user_id,
        }
        return JSResponse({"token": security.generate_token(user_id), "user": user_out})

    raise ApiError(500, "Internal server error")


@router.get("/me")
async def me(user_id: str = Depends(require_user)):
    user = await store.get_user(user_id)
    if not user:
        raise ApiError(404, "User not found")
    return JSResponse(without_password(user))
