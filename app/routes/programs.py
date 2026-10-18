"""GET/POST /api/programs"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request

from .. import store
from ..http import ApiError, read_json, require_user
from ..jscompat import JSResponse, js_key, js_or, now_ms, truthy

router = APIRouter()


@router.get("/programs")
async def list_programs(user_id: str = Depends(require_user)):
    programs = await store.get_programs(user_id)
    if programs is None:
        raise ApiError(404, "User not found")
    return JSResponse({"programs": js_or(programs, [])})


@router.post("/programs")
async def add_program(request: Request, user_id: str = Depends(require_user)):
    body = await read_json(request)
    name, exec_ = body.get("name"), body.get("exec")

    if not truthy(name) or not truthy(exec_):
        raise ApiError(400, "Name and exec are required")

    program = {
        "id": str(uuid.uuid4()),
        "name": name,
        "iconUrl": js_or(body.get("iconUrl"), ""),
        "exec": exec_,
        "meta": js_or(body.get("meta"), {"source": "user"}),
        "addedAt": now_ms(),
    }
    entry = {"ts": now_ms(), "type": "info", "msg": f"Added program: {js_key(name)}", "raw": program}
    await store.add_program(user_id, program, entry)
    return JSResponse({"success": True, "program": program})
