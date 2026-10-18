"""PostgreSQL data access. Every function returns/accepts Mongo-shaped dicts, so routes
and the WebSocket relay produce exactly the JSON the old server did."""

from __future__ import annotations

import json
import logging
from importlib import resources
from typing import Any

import asyncpg
from bson import ObjectId

from . import docmap
from .config import Settings
from .jscompat import dumps, js_key, to_jsonable

log = logging.getLogger("linkium.store")

_pool: asyncpg.Pool | None = None
_settings: Settings | None = None


class Conflict(Exception):
    """A unique constraint (email or pairing code) was violated."""


# --------------------------------------------------------------------------- lifecycle
async def connect(settings: Settings) -> None:
    global _pool, _settings
    _settings = settings
    _pool = await asyncpg.create_pool(
        settings.database_url,
        min_size=1,
        max_size=settings.db_pool_size,
        command_timeout=15,
        server_settings={"application_name": "linkium-api", "timezone": "UTC"},
    )
    async with _pool.acquire() as conn:
        await conn.execute(resources.files("app").joinpath("schema.sql").read_text())
    log.info("Connected to PostgreSQL")


async def close() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        log.info("PostgreSQL pool closed")


def pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database not connected")
    return _pool


def _log_cap() -> int:
    return _settings.activity_log_max if _settings else 0


# --------------------------------------------------------------------------- reads
async def _assemble(conn: asyncpg.Connection, urow: asyncpg.Record) -> dict[str, Any]:
    uid = urow["id"]
    prows = await conn.fetch("SELECT * FROM programs WHERE user_id = $1 ORDER BY position", uid)
    arows = await conn.fetch("SELECT * FROM activity_log WHERE user_id = $1 ORDER BY seq", uid)
    children = {
        "programs": [docmap.from_row(r, docmap.PROGRAM_FIELDS, r["extra"]) for r in prows],
        "activityLog": [docmap.from_row(r, docmap.ACTIVITY_FIELDS, r["extra"]) for r in arows],
    }
    doc = docmap.from_row(urow, docmap.USER_FIELDS, urow["extra"], children)
    return {"_id": uid, **doc}


async def find_user_by_email(email: str) -> dict[str, Any] | None:
    async with pool().acquire() as conn:
        urow = await conn.fetchrow("SELECT * FROM users WHERE email = $1", email)
        return await _assemble(conn, urow) if urow else None


async def get_user(user_id: str) -> dict[str, Any] | None:
    async with pool().acquire() as conn:
        urow = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
        return await _assemble(conn, urow) if urow else None


async def get_programs(user_id: str) -> list[Any] | None:
    """None if the user doesn't exist. Mirrors `user.programs || []`."""
    async with pool().acquire() as conn:
        urow = await conn.fetchrow("SELECT extra FROM users WHERE id = $1", user_id)
        if not urow:
            return None
        extra = json.loads(urow["extra"])
        if "programs" in extra:  # odd legacy value kept verbatim
            return extra["programs"]
        rows = await conn.fetch("SELECT * FROM programs WHERE user_id = $1 ORDER BY position", user_id)
        return [docmap.from_row(r, docmap.PROGRAM_FIELDS, r["extra"]) for r in rows]


async def get_activity(user_id: str) -> list[Any] | None:
    async with pool().acquire() as conn:
        urow = await conn.fetchrow("SELECT extra FROM users WHERE id = $1", user_id)
        if not urow:
            return None
        extra = json.loads(urow["extra"])
        if "activityLog" in extra:
            return extra["activityLog"]
        rows = await conn.fetch("SELECT * FROM activity_log WHERE user_id = $1 ORDER BY seq", user_id)
        return [docmap.from_row(r, docmap.ACTIVITY_FIELDS, r["extra"]) for r in rows]


async def code_taken_by_other(code: Any, user_id: str) -> bool:
    return bool(
        await pool().fetchval(
            "SELECT 1 FROM users WHERE pairing_code = $1::jsonb AND id <> $2", dumps(code), user_id
        )
    )


async def user_id_by_code(code: Any) -> str | None:
    if isinstance(code, (dict, list)) or code is None:
        return None
    return await pool().fetchval("SELECT id FROM users WHERE pairing_code = $1::jsonb", dumps(code))


async def pairing_code_of(user_id: str) -> Any:
    raw = await pool().fetchval("SELECT pairing_code FROM users WHERE id = $1", user_id)
    return json.loads(raw) if raw is not None else None


# --------------------------------------------------------------------------- write helpers
async def _lock_user(conn: asyncpg.Connection, user_id: str) -> dict[str, Any] | None:
    """Row-lock the user for the rest of the transaction; returns its `extra`."""
    raw = await conn.fetchval("SELECT extra FROM users WHERE id = $1 FOR UPDATE", user_id)
    return None if raw is None else json.loads(raw)


def _absent_only(extra: dict[str, Any], key: str) -> list[str]:
    """For $push: clear `key` unless it is a legacy list we must append to."""
    return [] if isinstance(extra.get(key), list) else [key]


async def _clear_overrides(conn: asyncpg.Connection, user_id: str, extra: dict[str, Any], keys: list[str]) -> None:
    """A write to a field makes it a normal column value again."""
    changed = False
    for key in keys:
        if key in extra:
            del extra[key]
            changed = True
    absent = extra.get(docmap.ABSENT)
    if absent:
        remaining = [k for k in absent if k not in keys]
        if remaining != absent:
            changed = True
            if remaining:
                extra[docmap.ABSENT] = remaining
            else:
                del extra[docmap.ABSENT]
    if changed:
        await conn.execute("UPDATE users SET extra = $2::json WHERE id = $1", user_id, docmap.dump_extra(extra))


async def _append_to_legacy_list(
    conn: asyncpg.Connection, user_id: str, extra: dict[str, Any], key: str, item: dict[str, Any], cap: int = 0
) -> bool:
    """If `key` is stored verbatim in extra (a migrated list holding non-objects), $push into it."""
    current = extra.get(key)
    if not isinstance(current, list):
        return False
    current.append(to_jsonable(item))
    if cap > 0:
        del current[:-cap]
    await conn.execute("UPDATE users SET extra = $2::json WHERE id = $1", user_id, docmap.dump_extra(extra))
    return True


async def _insert_activity(
    conn: asyncpg.Connection, user_id: str, entry: dict[str, Any], extra: dict[str, Any] | None = None
) -> None:
    if extra is not None and await _append_to_legacy_list(conn, user_id, extra, "activityLog", entry, _log_cap()):
        return
    row, extra = docmap.to_row(entry, docmap.ACTIVITY_FIELDS)
    await conn.execute(
        "INSERT INTO activity_log (user_id, ts, type, msg, raw, extra) VALUES ($1, $2, $3, $4, $5::json, $6::json)",
        user_id, row["ts"], row["type"], row["msg"], row["raw"], docmap.dump_extra(extra),
    )
    cap = _log_cap()
    if cap > 0:
        await conn.execute(
            """DELETE FROM activity_log WHERE user_id = $1 AND seq <= (
                   SELECT seq FROM activity_log WHERE user_id = $1 ORDER BY seq DESC OFFSET $2 LIMIT 1)""",
            user_id, cap,
        )


async def _insert_programs(conn: asyncpg.Connection, user_id: str, programs: list[dict[str, Any]], start: int) -> None:
    records = []
    for i, program in enumerate(programs):
        row, extra = docmap.to_row(program, docmap.PROGRAM_FIELDS)
        records.append(
            (user_id, start + i, row["program_id"], row["name"], row["icon_url"], row["exec"], row["meta"],
             row["added_at"], docmap.dump_extra(extra))
        )
    if records:
        await conn.executemany(
            """INSERT INTO programs (user_id, position, program_id, name, icon_url, exec, meta, added_at, extra)
               VALUES ($1, $2, $3, $4, $5, $6, $7::json, $8, $9::json)""",
            records,
        )


# --------------------------------------------------------------------------- writes
async def create_user(email: str, password_hash: str, first_entry: dict[str, Any], created_at) -> str:
    """Returns the new ObjectId hex. Raises Conflict if the email exists."""
    user_id = str(ObjectId())
    async with pool().acquire() as conn, conn.transaction():
        try:
            await conn.execute(
                "INSERT INTO users (id, email, password_hash, programs_fetched, created_at) VALUES ($1, $2, $3, false, $4)",
                user_id, email, password_hash, created_at,
            )
        except asyncpg.UniqueViolationError:
            raise Conflict("email") from None
        await _insert_activity(conn, user_id, first_entry)
    return user_id


async def set_pairing_code(user_id: str, code: Any, entry: dict[str, Any]) -> None:
    async with pool().acquire() as conn, conn.transaction():
        extra = await _lock_user(conn, user_id)
        if extra is None:
            return  # old server: updateOne matched nothing, still "success"
        try:
            await conn.execute("UPDATE users SET pairing_code = $2::jsonb WHERE id = $1", user_id, dumps(code))
        except asyncpg.UniqueViolationError:
            raise Conflict("pairingCode") from None
        await _clear_overrides(conn, user_id, extra, ["pairingCode", *_absent_only(extra, "activityLog")])
        await _insert_activity(conn, user_id, entry, extra)


async def add_program(user_id: str, program: dict[str, Any], entry: dict[str, Any]) -> None:
    async with pool().acquire() as conn, conn.transaction():
        extra = await _lock_user(conn, user_id)
        if extra is None:
            return
        await _clear_overrides(conn, user_id, extra, [*_absent_only(extra, "programs"), *_absent_only(extra, "activityLog")])
        if not await _append_to_legacy_list(conn, user_id, extra, "programs", program):
            nxt = await conn.fetchval("SELECT coalesce(max(position) + 1, 0) FROM programs WHERE user_id = $1", user_id)
            await _insert_programs(conn, user_id, [program], nxt)
        await _insert_activity(conn, user_id, entry, extra)


async def add_activity(user_id: str, entry: dict[str, Any]) -> None:
    async with pool().acquire() as conn, conn.transaction():
        extra = await _lock_user(conn, user_id)
        if extra is None:
            return
        await _clear_overrides(conn, user_id, extra, _absent_only(extra, "activityLog"))
        await _insert_activity(conn, user_id, entry, extra)


async def replace_programs(
    user_id: str, programs: list[dict[str, Any]], entry: dict[str, Any], keep_user_added: bool
) -> None:
    """Receiver sync: `$set programs` + `programsFetched: true` + log entry, atomically."""
    async with pool().acquire() as conn, conn.transaction():
        extra = await _lock_user(conn, user_id)
        if extra is None:
            return
        final = list(programs)
        if keep_user_added:
            existing = [
                docmap.from_row(r, docmap.PROGRAM_FIELDS, r["extra"])
                for r in await conn.fetch("SELECT * FROM programs WHERE user_id = $1 ORDER BY position", user_id)
            ]
            ids = {js_key(p.get("id")) for p in programs}
            final += [
                p for p in existing
                if isinstance(p.get("meta"), dict) and p["meta"].get("source") == "user" and js_key(p.get("id")) not in ids
            ]
        await conn.execute("DELETE FROM programs WHERE user_id = $1", user_id)
        await _insert_programs(conn, user_id, final, 0)
        await conn.execute("UPDATE users SET programs_fetched = true WHERE id = $1", user_id)
        await _clear_overrides(conn, user_id, extra, ["programs", "programsFetched", *_absent_only(extra, "activityLog")])
        await _insert_activity(conn, user_id, entry, extra)


async def change_pairing_code(user_id: str, new_code: Any) -> None:
    async with pool().acquire() as conn, conn.transaction():
        extra = await _lock_user(conn, user_id)
        if extra is None:
            return
        try:
            await conn.execute("UPDATE users SET pairing_code = $2::jsonb WHERE id = $1", user_id, dumps(new_code))
        except asyncpg.UniqueViolationError:
            raise Conflict("pairingCode") from None
        await _clear_overrides(conn, user_id, extra, ["pairingCode"])
