"""WebSocket relay at /ws — same protocol as the old `ws` server.

Protocol (unchanged):
  * A client registers by sending {"role": "sender"|"receiver", "code": <pairing code>}.
    Nothing is sent back.
  * Messages from a sender are forwarded verbatim to every receiver on the same code.
  * Messages from a receiver are forwarded to every sender on the same code. Two
    receiver messages also touch the database:
      {"programs": [...]}  -> saved as the paired user's program list
      {"new_code": "..."}  -> the paired user's pairingCode is changed
  * Dead connections are dropped by protocol-level ping/pong (uvicorn --ws-ping-*).

Fixes over the old server (none change what well-behaved clients see):
  * After a `new_code`, later program syncs are saved to the right user
    (the old server kept querying the stale code and silently lost them).
  * Re-registering no longer leaves a ghost copy of the connection in the old group.
  * Unknown roles and object-valued codes (Mongo operator injection) are rejected.
  * A new_code that belongs to another account is refused instead of hijacking it.
  * Per-connection rate limiting, a message size cap, and send timeouts so one slow
    client cannot stall a whole group.
  * Optional: senders must present a JWT (WS_REQUIRE_AUTH=true) and browser origins
    can be checked (WS_ENFORCE_ORIGIN=true). Both are off by default for compatibility.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket
from starlette.websockets import WebSocketState

from . import security, store
from .config import Settings
from .jscompat import js_key, js_or, now_ms, truthy
from .ratelimit import TokenBucket
from .routes.pairing import valid_code

log = logging.getLogger("linkium.ws")

SEND_TIMEOUT = 10.0
ROLES = ("sender", "receiver")


@dataclass(eq=False)
class Connection:
    ws: WebSocket
    bucket: TokenBucket
    role: str | None = None
    code: Any = None  # exactly as the client sent it
    key: str | None = None  # routing key (JS object-key coercion of code)
    db_code: Any = None  # code to use for DB lookups; follows new_code updates
    user_id: str | None = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class Relay:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.groups: dict[str, dict[str, list[Connection]]] = {}
        self.all: set[Connection] = set()

    # ---------------------------------------------------------------- registry
    def register(self, conn: Connection, role: str, code: Any) -> None:
        if conn.role:
            self.unregister(conn)
        conn.role, conn.code, conn.key, conn.db_code = role, code, js_key(code), code
        group = self.groups.setdefault(conn.key, {"senders": [], "receivers": []})
        group["senders" if role == "sender" else "receivers"].append(conn)
        log.info("%s connected | code: %s", role, conn.key)

    def unregister(self, conn: Connection) -> None:
        if not conn.role or conn.key is None:
            return
        group = self.groups.get(conn.key)
        if group:
            bucket = group["senders" if conn.role == "sender" else "receivers"]
            if conn in bucket:
                bucket.remove(conn)
            if not group["senders"] and not group["receivers"]:
                del self.groups[conn.key]
        log.info("%s disconnected | code: %s", conn.role, conn.key)
        conn.role = conn.code = conn.key = conn.db_code = None

    # ---------------------------------------------------------------- sending
    async def _send(self, conn: Connection, text: str) -> None:
        if conn.ws.application_state != WebSocketState.CONNECTED:
            return
        try:
            async with conn.lock:
                await asyncio.wait_for(conn.ws.send_text(text), SEND_TIMEOUT)
        except asyncio.TimeoutError:
            log.warning("Send timed out; closing slow %s on code %s", conn.role, conn.key)
            await self._close(conn, 1011)
        except Exception:  # client went away mid-send
            pass

    async def forward(self, key: str, target: str, text: str) -> None:
        group = self.groups.get(key)
        if not group:
            return
        targets = list(group[target])
        if targets:
            await asyncio.gather(*(self._send(c, text) for c in targets))

    async def _close(self, conn: Connection, code: int = 1000) -> None:
        try:
            await conn.ws.close(code)
        except Exception:
            pass

    async def close_all(self) -> None:
        await asyncio.gather(*(self._close(c, 1001) for c in list(self.all)), return_exceptions=True)

    # ---------------------------------------------------------------- endpoint
    async def handle(self, websocket: WebSocket) -> None:
        cfg = self.settings
        origin = websocket.headers.get("origin")
        if cfg.ws_enforce_origin and origin and origin not in cfg.cors_origins:
            log.warning("WS origin rejected: %s", origin)
            await websocket.close(code=1008)
            return

        await websocket.accept()
        conn = Connection(ws=websocket, bucket=TokenBucket(cfg.ws_rate_per_second, cfg.ws_rate_burst))
        query_token = websocket.query_params.get("token")
        if query_token:
            conn.user_id = security.verify_token(query_token)
        self.all.add(conn)
        dropped = 0

        try:
            while True:
                message = await websocket.receive()
                if message["type"] == "websocket.disconnect":
                    break
                text = message.get("text")
                if text is None:
                    raw = message.get("bytes")
                    if raw is None:
                        continue
                    try:
                        text = raw.decode("utf-8")
                    except UnicodeDecodeError:
                        continue

                if not conn.bucket.allow():
                    dropped += 1
                    if dropped in (1, 100) or dropped % 1000 == 0:
                        log.warning("Rate limit: dropped %d messages from %s/%s", dropped, conn.role, conn.key)
                    continue

                try:
                    await self.on_message(conn, text)
                except Exception:
                    log.exception("WS message error")
        except Exception as exc:  # abrupt network errors
            log.debug("WS error: %s", exc)
        finally:
            self.unregister(conn)
            self.all.discard(conn)

    async def on_message(self, conn: Connection, text: str) -> None:
        try:
            msg = json.loads(text)
        except ValueError:
            log.debug("Ignoring non-JSON WS message")
            return
        if msg is None:  # the old server crashed on `null.role` and dropped it
            return

        if isinstance(msg, dict) and truthy(msg.get("role")) and truthy(msg.get("code")):
            await self.on_register(conn, msg)
            return

        if not conn.role or conn.key is None:
            log.warning("Unregistered connection message")
            return

        if conn.role == "sender":
            await self.forward(conn.key, "receivers", text)
        else:
            await self.on_receiver_message(conn, msg, text)

    async def on_register(self, conn: Connection, msg: dict[str, Any]) -> None:
        role, code = msg.get("role"), msg.get("code")
        if role not in ROLES:
            log.warning("Rejected registration with unknown role %r", role)
            return
        if not valid_code(code, self.settings.ws_max_code_length):
            log.warning("Rejected registration with invalid code")
            return

        token = msg.get("token")
        if isinstance(token, str) and token:
            conn.user_id = security.verify_token(token) or conn.user_id

        if self.settings.ws_require_auth and role == "sender":
            if not conn.user_id or not await self._user_owns_code(conn.user_id, code):
                log.warning("Rejected unauthenticated sender for code %s", js_key(code))
                return

        self.register(conn, role, code)

    async def _user_owns_code(self, user_id: str, code: Any) -> bool:
        try:
            owned = await store.pairing_code_of(user_id)
        except Exception:
            log.exception("DB error during WS auth")
            return False
        return owned is not None and js_key(owned) == js_key(code)

    # ---------------------------------------------------------------- receiver
    async def on_receiver_message(self, conn: Connection, msg: Any, text: str) -> None:
        key = conn.key
        assert key is not None

        if isinstance(msg, dict) and isinstance(msg.get("programs"), list):
            await self._save_programs(conn, msg["programs"])
        elif isinstance(msg, dict) and truthy(msg.get("new_code")):
            await self._change_code(conn, msg["new_code"])

        await self.forward(key, "senders", text)

    async def _save_programs(self, conn: Connection, incoming: list[Any]) -> None:
        try:
            user_id = await store.user_id_by_code(conn.db_code)
            if not user_id:
                return

            programs = []
            for p in incoming:
                p = p if isinstance(p, dict) else {}
                programs.append(
                    {
                        "id": js_or(p.get("id"), p.get("name")),
                        "name": p.get("name"),
                        "iconUrl": js_or(p.get("iconUrl"), p.get("icon"), ""),
                        "exec": js_or(p.get("exec"), ""),
                        "meta": js_or(p.get("meta"), {"source": "receiver"}),
                        "addedAt": now_ms(),
                    }
                )
            count = len(programs)
            entry = {"ts": now_ms(), "type": "info", "msg": f"Program list updated ({count})", "raw": {"count": count}}
            await store.replace_programs(user_id, programs, entry, self.settings.preserve_user_programs)
            log.info("Programs saved for code %s", js_key(conn.db_code))
        except Exception:
            log.exception("DB error while saving programs")

    async def _change_code(self, conn: Connection, new_code: Any) -> None:
        if not valid_code(new_code, self.settings.ws_max_code_length):
            log.warning("Ignored invalid new_code")
            return
        try:
            user_id = await store.user_id_by_code(conn.db_code)
            if user_id:
                if await store.code_taken_by_other(new_code, user_id):
                    log.warning("Refused new_code %s: it belongs to another account", js_key(new_code))
                    return
                try:
                    await store.change_pairing_code(user_id, new_code)
                except store.Conflict:
                    log.warning("Refused new_code %s: it belongs to another account", js_key(new_code))
                    return
            log.info("Code updated %s -> %s", js_key(conn.db_code), js_key(new_code))
            # Routing stays on the registered code (same as before); DB lookups follow the new one.
            conn.db_code = new_code
        except Exception:
            log.exception("Code update error")
