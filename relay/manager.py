"""In-memory pairing state. Same rules as the old ConnectionManager:
one receiver per code, any number of senders, senders need a live receiver.

Fixes:
  * a receiver that registers a second code releases the first (the old code kept
    both, and cleanup freed only one, leaving the other "in use" until a restart)
  * the per-IP connection check and increment are atomic
  * sends run concurrently, are serialized per socket, and time out
  * O(1) lookups instead of scanning every receiver per message
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import WebSocket

log = logging.getLogger("relay")


class ConnectionManager:
    def __init__(self, max_per_ip: int, send_timeout: float = 10.0) -> None:
        self.max_per_ip = max_per_ip
        self.send_timeout = send_timeout
        self._receivers: dict[str, WebSocket] = {}  # code -> receiver
        self._receiver_code: dict[WebSocket, str] = {}  # receiver -> code
        self._sender_to_code: dict[WebSocket, str] = {}
        self._senders_by_code: dict[str, set[WebSocket]] = {}
        self._ip_counts: dict[str, int] = {}
        self._send_locks: dict[WebSocket, asyncio.Lock] = {}

    # ---------------------------------------------------------------- per-IP limit
    def try_connect(self, ip: str) -> bool:
        """Check and count in one step (no await in between, so it's atomic)."""
        if self._ip_counts.get(ip, 0) >= self.max_per_ip:
            return False
        self._ip_counts[ip] = self._ip_counts.get(ip, 0) + 1
        return True

    def track_disconnect(self, ip: str) -> None:
        count = self._ip_counts.get(ip, 1) - 1
        if count <= 0:
            self._ip_counts.pop(ip, None)
        else:
            self._ip_counts[ip] = count

    # ---------------------------------------------------------------- registration
    def register_receiver(self, code: str, ws: WebSocket) -> tuple[bool, str | None]:
        """Returns (ok, code released because this socket moved to a new code)."""
        existing = self._receivers.get(code)
        if existing is not None and existing is not ws:
            return False, None
        released = None
        old = self._receiver_code.get(ws)
        if old is not None and old != code:
            del self._receivers[old]
            released = old
        self._receivers[code] = ws
        self._receiver_code[ws] = code
        return True, released

    def register_sender(self, code: str, ws: WebSocket) -> bool:
        if code not in self._receivers:
            return False
        old = self._sender_to_code.get(ws)
        if old is not None:
            self._senders_by_code.get(old, set()).discard(ws)
        self._sender_to_code[ws] = code
        self._senders_by_code.setdefault(code, set()).add(ws)
        return True

    def is_receiver(self, ws: WebSocket) -> bool:
        return ws in self._receiver_code

    def is_sender(self, ws: WebSocket) -> bool:
        return ws in self._sender_to_code

    # ---------------------------------------------------------------- sending
    async def send(self, ws: WebSocket, payload: str) -> bool:
        lock = self._send_locks.setdefault(ws, asyncio.Lock())
        try:
            async with lock:
                await asyncio.wait_for(ws.send_text(payload), self.send_timeout)
            return True
        except asyncio.TimeoutError:
            log.warning("Send timed out; closing slow client")
            try:
                await ws.close(code=1011)
            except Exception:
                pass
            return False
        except Exception:
            return False

    async def relay_to_receiver(self, ws: WebSocket, payload: str) -> bool:
        code = self._sender_to_code.get(ws)
        receiver = self._receivers.get(code) if code else None
        if receiver is None:
            return False
        await self.send(receiver, payload)
        return True

    async def relay_to_senders(self, ws: WebSocket, payload: str) -> bool:
        code = self._receiver_code.get(ws)
        if not code:
            return False
        targets = list(self._senders_by_code.get(code, ()))
        if not targets:
            return False
        results = await asyncio.gather(*(self.send(s, payload) for s in targets))
        return any(results)

    # ---------------------------------------------------------------- cleanup
    def cleanup(self, ws: WebSocket) -> str | None:
        """Forget a socket. Returns the receiver code it freed, if any."""
        self._send_locks.pop(ws, None)
        code = self._sender_to_code.pop(ws, None)
        if code is not None:
            peers = self._senders_by_code.get(code)
            if peers is not None:
                peers.discard(ws)
                if not peers:
                    del self._senders_by_code[code]
        freed = self._receiver_code.pop(ws, None)
        if freed is not None and self._receivers.get(freed) is ws:
            del self._receivers[freed]
        return freed

    # ---------------------------------------------------------------- status
    @property
    def active_codes(self) -> list[str]:
        return list(self._receivers.keys())

    @property
    def senders_count(self) -> int:
        return len(self._sender_to_code)

    @property
    def receivers_count(self) -> int:
        return len(self._receivers)
