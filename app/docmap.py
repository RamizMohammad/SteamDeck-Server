"""Mapping between Mongo-shaped documents (what the API returns) and table rows.

Typed columns hold the normal case. Anything else is stored losslessly in the
row's `extra` JSON object:
  * a known field whose value has an unexpected type -> extra[field] = original value
  * a field the schema doesn't know                -> extra[field] = value
  * a known field that was missing from the doc     -> listed in extra["$absent"]
(Mongo field names cannot start with "$", so "$absent" can never collide.)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from .jscompat import dumps, js_key, to_jsonable, truthy

ABSENT = "$absent"

# (document key, column, kind)
USER_FIELDS = [
    ("email", "email", "text"),
    ("passwordHash", "password_hash", "text"),
    ("programsFetched", "programs_fetched", "bool"),
    ("programs", None, "child"),
    ("activityLog", None, "child"),
    ("createdAt", "created_at", "ts"),
    ("pairingCode", "pairing_code", "jsonb"),
]
PROGRAM_FIELDS = [
    ("id", "program_id", "text"),
    ("name", "name", "text"),
    ("iconUrl", "icon_url", "text"),
    ("exec", "exec", "text"),
    ("meta", "meta", "json"),
    ("addedAt", "added_at", "ts"),
]
ACTIVITY_FIELDS = [
    ("ts", "ts", "ts"),
    ("type", "type", "text"),
    ("msg", "msg", "text"),
    ("raw", "raw", "json"),
]


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def to_row(doc: dict[str, Any], fields: list[tuple[str, str | None, str]]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Split a document into column values and the `extra` object."""
    row: dict[str, Any] = {}
    extra: dict[str, Any] = {}
    absent: list[str] = []
    known = set()

    for key, col, kind in fields:
        known.add(key)
        if kind == "child":
            if key not in doc:
                absent.append(key)
            elif not isinstance(doc[key], list):
                extra[key] = to_jsonable(doc[key])
            continue
        assert col is not None
        if key not in doc:
            if kind != "jsonb":  # a NULL pairing_code already means "never set"
                absent.append(key)
            row[col] = None if kind != "bool" else False
            continue

        value = doc[key]
        if kind == "text":
            if value is None or isinstance(value, str):
                row[col] = value
            else:
                row[col] = js_key(value)  # searchable approximation; exact value in extra
                extra[key] = to_jsonable(value)
        elif kind == "bool":
            row[col] = value if isinstance(value, bool) else truthy(value)
            if not isinstance(value, bool):
                extra[key] = to_jsonable(value)
        elif kind == "ts":
            if isinstance(value, datetime):
                row[col] = _aware(value)
            else:
                row[col] = None
                extra[key] = to_jsonable(value)
        elif kind == "json":
            row[col] = dumps(value)
        elif kind == "jsonb":
            if value is None or isinstance(value, (dict, list)):
                row[col] = None  # never index objects/null as a pairing code
                extra[key] = to_jsonable(value)
            else:
                row[col] = dumps(value)

    for key, value in doc.items():
        if key not in known and key != "_id":
            extra[key] = to_jsonable(value)
    if absent:
        extra[ABSENT] = absent
    return row, extra


def from_row(
    row: Any, fields: list[tuple[str, str | None, str]], extra_json: str | None, children: dict[str, list] | None = None
) -> dict[str, Any]:
    """Rebuild the document. `children` supplies programs/activityLog lists for users."""
    extra = json.loads(extra_json) if extra_json else {}
    absent = set(extra.pop(ABSENT, []))
    out: dict[str, Any] = {}
    known = set()

    for key, col, kind in fields:
        known.add(key)
        if key in absent:
            continue
        if key in extra:
            out[key] = extra[key]
            continue
        if kind == "child":
            out[key] = (children or {}).get(key, [])
            continue
        value = row[col]
        if kind in ("json", "jsonb"):
            if value is None:
                if kind == "jsonb":
                    continue  # pairingCode never set
                value = None
            else:
                value = json.loads(value)
        out[key] = value

    for key, value in extra.items():
        if key not in known:
            out[key] = value
    return out


def dump_extra(extra: dict[str, Any]) -> str:
    return dumps(extra) if extra else "{}"
