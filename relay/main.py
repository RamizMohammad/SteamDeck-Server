"""Linkium WebSocket relay — drop-in replacement for ssh_linkium_server/DeployServer.py.

Wire protocol (unchanged):
  {"role":"receiver","code":C} -> {"status":"registered","code":C}
                               |  {"error":"Code already in use by another receiver"}
  {"role":"sender","code":C}   -> {"status":"linked","code":C}
                               |  {"error":"No receiver found for that code"}
  anything else from a sender  -> forwarded verbatim to the receiver of its code
  anything else from receiver  -> forwarded verbatim to every sender of its code
  errors: "Message too large", "Invalid JSON", "Message must be a JSON object",
          "Invalid pairing code format", "Register as sender or receiver first"
HTTP: GET /  GET /ping  GET /status (same shapes)

Fixes over the old relay (none change what well-behaved clients see):
  * /status no longer publishes live pairing codes; they appear only with
    `Authorization: Bearer $RELAY_STATUS_TOKEN` (counts stay public)
  * client IP comes from the entry our own nginx appended to X-Forwarded-For,
    so the per-IP limit can't be dodged with a spoofed header
  * failed sender links are slowed down (tarpit) so codes can't be brute-forced;
    the replies are unchanged
  * non-string codes and binary frames get a normal error instead of killing the socket
  * see manager.py and persist.py for the rest
"""

from __future__ import annotations

import asyncio
import hmac
import json
import logging
import re
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, WebSocket, status

from app.ratelimit import SlidingWindow, TokenBucket

from .config import RelaySettings, load_relay_settings
from .manager import ConnectionManager
from .persist import Persistence

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("relay")

CODE_PATTERN = re.compile(r"^[A-Za-z0-9_\-]{4,32}$")


def validate_code(code) -> bool:
    return isinstance(code, str) and bool(code) and bool(CODE_PATTERN.match(code))


def client_ip(headers, client, hops: int) -> str:
    """The address our trusted proxy saw. With hops=1 that's the LAST X-Forwarded-For
    entry (nginx appends it); earlier entries are whatever the client claimed."""
    xff = [p.strip() for p in headers.get("x-forwarded-for", "").split(",") if p.strip()]
    if hops > 0 and xff:
        return xff[-hops] if len(xff) >= hops else xff[0]
    return client.host if client else "unknown"


async def send_error(ws: WebSocket, message: str) -> None:
    try:
        await ws.send_json({"error": message})
    except Exception:
        pass


def create_relay_app(settings: RelaySettings | None = None) -> FastAPI:
    settings = settings or load_relay_settings()
    manager = ConnectionManager(settings.max_connections_per_ip, settings.send_timeout)
    persist = Persistence(settings)
    fail_by_ip = SlidingWindow(settings.fail_per_ip_10min, 600)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await persist.start()
        yield
        await persist.stop()

    app = FastAPI(title="Linkium Relay", version="2.0.0", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.manager = manager
    app.state.persist = persist
    app.state.settings = settings

    @app.get("/")
    def home():
        return {"status": "ok", "message": "Linkium WebSocket Relay v2"}

    @app.get("/ping")
    def ping():
        return {"alive": True, "timestamp": time.time()}

    @app.get("/status")
    def relay_status(request: Request):
        auth = request.headers.get("authorization", "")
        show = bool(settings.status_token) and hmac.compare_digest(auth, f"Bearer {settings.status_token}")
        return {
            "active_codes": manager.active_codes if show else [],
            "senders_count": manager.senders_count,
            "receivers_count": manager.receivers_count,
        }

    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket):
        ip = client_ip(ws.headers, ws.client, settings.trusted_proxy_hops)

        if settings.allowed_origins:
            origin = ws.headers.get("origin", "")
            if origin not in settings.allowed_origins:
                await ws.close(code=status.WS_1008_POLICY_VIOLATION)
                logger.warning("Rejected WS from origin '%s'", origin)
                return

        if not manager.try_connect(ip):
            await ws.close(code=status.WS_1008_POLICY_VIOLATION)
            logger.warning("Connection limit hit for IP %s", ip)
            return

        try:
            await ws.accept()
        except Exception:
            manager.track_disconnect(ip)
            return
        logger.info("WS connected: %s", ip)
        bucket = TokenBucket(settings.ws_rate_per_second, settings.ws_rate_burst)
        failed_links = 0

        try:
            while True:
                message = await ws.receive()
                if message["type"] == "websocket.disconnect":
                    break
                raw = message.get("text")
                if raw is None:
                    data = message.get("bytes") or b""
                    try:
                        raw = data.decode("utf-8")
                    except UnicodeDecodeError:
                        await send_error(ws, "Invalid JSON")
                        continue

                if not bucket.allow():
                    continue  # flood: drop silently

                if len(raw.encode()) > settings.max_message_bytes:
                    await send_error(ws, "Message too large")
                    continue

                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    await send_error(ws, "Invalid JSON")
                    continue

                if not isinstance(msg, dict):
                    await send_error(ws, "Message must be a JSON object")
                    continue

                role = msg.get("role")

                if role == "receiver":
                    code = msg.get("code", "")
                    if not validate_code(code):
                        await send_error(ws, "Invalid pairing code format")
                        continue
                    ok, released = manager.register_receiver(code, ws)
                    if not ok:
                        await send_error(ws, "Code already in use by another receiver")
                        continue
                    if released:
                        persist.code_freed(released)
                    logger.info("Receiver registered: code=%s ip=%s", code, ip)
                    await ws.send_json({"status": "registered", "code": code})
                    persist.receiver_registered(code, ip)

                elif role == "sender":
                    code = msg.get("code", "")
                    if not validate_code(code):
                        await send_error(ws, "Invalid pairing code format")
                        continue
                    if not manager.register_sender(code, ws):
                        failed_links += 1
                        fail_by_ip.hit(ip)
                        if fail_by_ip.blocked(ip):
                            await asyncio.sleep(5)  # heavy tarpit for this IP
                        elif failed_links > settings.fail_tarpit_after:
                            await asyncio.sleep(1)
                        await send_error(ws, "No receiver found for that code")
                        continue
                    logger.info("Sender linked: code=%s ip=%s", code, ip)
                    await ws.send_json({"status": "linked", "code": code})
                    persist.sender_linked(code, ip)

                else:
                    if manager.is_sender(ws):
                        await manager.relay_to_receiver(ws, raw)
                        direction = "sender->receiver"
                    elif manager.is_receiver(ws):
                        await manager.relay_to_senders(ws, raw)
                        direction = "receiver->senders"
                    else:
                        await send_error(ws, "Register as sender or receiver first")
                        continue
                    persist.message(direction, ip, len(raw))

        except Exception as exc:
            logger.debug("WS error from %s: %s", ip, exc)
        finally:
            freed = manager.cleanup(ws)
            manager.track_disconnect(ip)
            if freed:
                persist.code_freed(freed)
            logger.info("Cleaned up: %s (freed code: %s)", ip, freed)

    return app
