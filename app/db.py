"""MongoDB access. Same database ("streamdeck") and collection ("users") as the old server."""

from __future__ import annotations

import logging
from typing import Any

from pymongo import ASCENDING, AsyncMongoClient
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.errors import PyMongoError

from .config import Settings

log = logging.getLogger("linkium.db")

_client: AsyncMongoClient | None = None
_users: AsyncCollection | None = None
_settings: Settings | None = None


async def connect(settings: Settings) -> None:
    global _client, _users, _settings
    _settings = settings
    _client = AsyncMongoClient(
        settings.mongodb_uri,
        tz_aware=True,
        serverSelectionTimeoutMS=10_000,
        appname="linkium-api",
    )
    await _client.admin.command("ping")
    _users = _client[settings.mongodb_db]["users"]
    log.info("Connected to MongoDB (db=%s)", settings.mongodb_db)
    await _ensure_indexes(_users)


async def _ensure_indexes(users: AsyncCollection) -> None:
    """Best effort: existing duplicate data must never stop the server from starting."""
    specs: list[tuple[str, dict[str, Any]]] = [
        ("email", {"unique": True, "name": "email_unique"}),
        (
            "pairingCode",
            {
                "name": "pairingCode_lookup",
                # non-unique: old data may already contain duplicates, uniqueness is enforced in code
            },
        ),
    ]
    for key, opts in specs:
        try:
            await users.create_index([(key, ASCENDING)], **opts)
        except PyMongoError as exc:
            log.warning("Could not create index on %s (%s). Continuing without it.", key, exc)


def users() -> AsyncCollection:
    if _users is None:
        raise RuntimeError("Database not connected")
    return _users


def activity_push(entry: dict[str, Any]) -> dict[str, Any]:
    """`$push` spec for one activity entry, capped to the newest N if configured."""
    limit = _settings.activity_log_max if _settings else 0
    if limit and limit > 0:
        return {"$each": [entry], "$slice": -limit}
    return entry  # type: ignore[return-value]


async def close() -> None:
    global _client, _users
    if _client is not None:
        await _client.close()
        _client = None
        _users = None
        log.info("MongoDB connection closed")
