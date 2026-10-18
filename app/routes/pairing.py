"""POST /api/pairing"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from .. import store
from ..http import ApiError, read_json, require_user
from ..jscompat import JSResponse, js_key, now_ms, truthy

router = APIRouter()

IN_USE = "Pairing code is already in use"


def valid_code(code, max_len: int) -> bool:
    """Codes are strings (or plain numbers); never objects, which would be query operators."""
    if isinstance(code, bool) or not isinstance(code, (str, int, float)):
        return False
    return len(js_key(code)) <= max_len


@router.post("/pairing")
async def set_pairing(request: Request, user_id: str = Depends(require_user)):
    body = await read_json(request)
    code = body.get("pairingCode")

    if not truthy(code):
        raise ApiError(400, "Pairing code is required")
    if not valid_code(code, request.app.state.settings.ws_max_code_length):
        raise ApiError(400, "Invalid pairing code")

    if await store.code_taken_by_other(code, user_id):
        raise ApiError(409, IN_USE)
    entry = {
        "ts": now_ms(),
        "type": "info",
        "msg": f"Pairing code set to {js_key(code)}",
        "raw": {"pairingCode": code},
    }
    try:
        await store.set_pairing_code(user_id, code, entry)
    except store.Conflict:  # lost a race for the same code
        raise ApiError(409, IN_USE) from None
    return JSResponse({"success": True, "pairingCode": code})
