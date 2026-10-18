"""Helpers that reproduce JavaScript / Express semantics exactly.

The frontend and the desktop receiver were written against the Node server,
so anything that reaches the wire (JSON formatting, dates, truthiness checks)
must behave the way JavaScript did.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from starlette.responses import JSONResponse

_MAX_SAFE_INT = 2**53


def now_ms() -> datetime:
    """Current UTC time truncated to milliseconds (JS Date / BSON precision)."""
    now = datetime.now(timezone.utc)
    return now.replace(microsecond=(now.microsecond // 1000) * 1000)


def js_iso(dt: datetime) -> str:
    """Format like JavaScript's Date.prototype.toJSON(): 2026-10-15T18:17:00.000Z"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def truthy(value: Any) -> bool:
    """JavaScript truthiness. Unlike Python, [] and {} are truthy in JS."""
    if value is None or value is False:
        return False
    if isinstance(value, bool):
        return True
    if isinstance(value, (int, float)):
        return not (value == 0 or (isinstance(value, float) and math.isnan(value)))
    if isinstance(value, str):
        return value != ""
    return True


def js_or(*values: Any) -> Any:
    """`a || b || c` in JavaScript."""
    for value in values[:-1]:
        if truthy(value):
            return value
    return values[-1]


def js_key(value: Any) -> str:
    """How JavaScript coerces a value when used as an object key."""
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "null"
    if isinstance(value, float) and value.is_integer() and abs(value) < _MAX_SAFE_INT:
        return str(int(value))
    if isinstance(value, (dict, list)):
        return "[object Object]" if isinstance(value, dict) else ",".join(js_key(v) for v in value)
    return str(value)


def to_jsonable(value: Any) -> Any:
    """Convert BSON/Python values into what JSON.stringify would have produced."""
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(v) for v in value]
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return js_iso(value)
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, str):
        return str(value)
    if isinstance(value, int):
        return int(value)  # bson.Int64 etc. -> plain int
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None  # JSON.stringify(NaN) -> null
        if value.is_integer() and abs(value) < _MAX_SAFE_INT:
            return int(value)  # JS prints 5, not 5.0
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    # Decimal128, Int64, etc.
    try:
        return to_jsonable(value.to_decimal())  # type: ignore[attr-defined]
    except AttributeError:
        return str(value)


def dumps(value: Any) -> str:
    return json.dumps(to_jsonable(value), ensure_ascii=False, separators=(",", ":"), allow_nan=False)


class JSResponse(JSONResponse):
    """JSON response byte-compatible with Express `res.json()`."""

    media_type = "application/json"

    def render(self, content: Any) -> bytes:
        return dumps(content).encode("utf-8")

    def init_headers(self, headers=None) -> None:  # type: ignore[override]
        super().init_headers(headers)
        # Express sends "application/json; charset=utf-8"
        self.raw_headers = [
            (k, b"application/json; charset=utf-8") if k == b"content-type" else (k, v)
            for k, v in self.raw_headers
        ]


def error(status: int, message: str) -> JSResponse:
    return JSResponse({"error": message}, status_code=status)
