"""GET/POST /api/activity"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from .. import store
from ..http import ApiError, read_json, require_user
from ..jscompat import JSResponse, js_or, now_ms, truthy

router = APIRouter()


@router.get("/activity")
async def list_activity(user_id: str = Depends(require_user)):
    log = await store.get_activity(user_id)
    if log is None:
        raise ApiError(404, "User not found")
    return JSResponse({"activityLog": js_or(log, [])})


@router.post("/activity")
async def add_activity(request: Request, user_id: str = Depends(require_user)):
    body = await read_json(request)
    type_, msg = body.get("type"), body.get("msg")

    if not truthy(type_) or not truthy(msg):
        raise ApiError(400, "Type and message are required")

    entry = {"ts": now_ms(), "type": type_, "msg": msg, "raw": js_or(body.get("raw"), {})}
    await store.add_activity(user_id, entry)
    return JSResponse({"success": True, "entry": entry})
