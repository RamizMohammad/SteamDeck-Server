"""Best-effort persistence for the relay, in PostgreSQL.

Relaying never waits on the database: events go into a bounded queue and a
single background task writes them in batches. If Postgres is down, the relay
keeps working (as the old one did without Mongo), reconnects every 30 s, and
drops events only when the queue is full.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import datetime, timedelta, timezone
from importlib import resources
from typing import Any

import asyncpg

from .config import RelaySettings

log = logging.getLogger("relay.persist")

QUEUE_MAX = 10_000
BATCH_MAX = 500
RECONNECT_EVERY = 30.0
PRUNE_EVERY = 3600.0


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Persistence:
    def __init__(self, settings: RelaySettings) -> None:
        self.settings = settings
        self.pool: asyncpg.Pool | None = None
        self.queue: asyncio.Queue[tuple[str, tuple[Any, ...]]] = asyncio.Queue(QUEUE_MAX)
        self.dropped = 0
        self._tasks: list[asyncio.Task] = []

    @property
    def enabled(self) -> bool:
        return bool(self.settings.database_url)

    # ------------------------------------------------------------------ lifecycle
    async def start(self) -> None:
        if not self.enabled:
            log.warning("DATABASE_URL not set: relay will work without persistence.")
            return
        await self._try_connect()
        self._tasks = [asyncio.create_task(self._writer()), asyncio.create_task(self._maintenance())]

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        if self.pool is not None:
            with contextlib.suppress(Exception):
                await self._flush_remaining()
            await self.pool.close()
            self.pool = None

    async def _try_connect(self) -> bool:
        try:
            self.pool = await asyncpg.create_pool(
                self.settings.database_url,
                min_size=1,
                max_size=4,
                command_timeout=15,
                server_settings={"application_name": "linkium-relay", "timezone": "UTC"},
            )
            async with self.pool.acquire() as conn:
                await conn.execute(resources.files("relay").joinpath("schema.sql").read_text())
                # Nothing is connected right after a restart
                await conn.execute("UPDATE relay_pairings SET active = false WHERE active")
            log.info("PostgreSQL ready.")
            return True
        except Exception as exc:
            log.warning("PostgreSQL unavailable: %s - relay will work without persistence for now.", exc)
            if self.pool is not None:
                with contextlib.suppress(Exception):
                    await self.pool.close()
            self.pool = None
            return False

    # ------------------------------------------------------------------ events (never block)
    def _put(self, kind: str, *args: Any) -> None:
        if not self.enabled:
            return
        try:
            self.queue.put_nowait((kind, args))
        except asyncio.QueueFull:
            self.dropped += 1
            if self.dropped in (1, 100) or self.dropped % 10_000 == 0:
                log.warning("Persistence queue full: dropped %d events", self.dropped)

    def receiver_registered(self, code: str, addr: str) -> None:
        self._put("receiver", code, addr, _now())

    def sender_linked(self, code: str, addr: str) -> None:
        self._put("sender", code, addr, _now())

    def code_freed(self, code: str) -> None:
        self._put("freed", code)

    def message(self, direction: str, addr: str, size: int) -> None:
        self._put("msg", direction, _now(), addr, size)

    # ------------------------------------------------------------------ writer
    async def _writer(self) -> None:
        while True:
            if self.pool is None:
                await asyncio.sleep(RECONNECT_EVERY)
                await self._try_connect()
                continue
            first = await self.queue.get()
            batch = [first]
            while len(batch) < BATCH_MAX and not self.queue.empty():
                batch.append(self.queue.get_nowait())
            try:
                await self._write(batch)
            except (OSError, asyncpg.PostgresConnectionError, asyncpg.InterfaceError) as exc:
                log.warning("PostgreSQL write failed (%s); will reconnect", exc)
                with contextlib.suppress(Exception):
                    await self.pool.close()
                self.pool = None
            except Exception:
                log.exception("Relay persistence batch failed; %d events skipped", len(batch))

    async def _flush_remaining(self) -> None:
        batch = []
        while not self.queue.empty():
            batch.append(self.queue.get_nowait())
        if batch:
            await self._write(batch)

    async def _write(self, batch: list[tuple[str, tuple[Any, ...]]]) -> None:
        assert self.pool is not None
        messages = [args for kind, args in batch if kind == "msg"]
        async with self.pool.acquire() as conn, conn.transaction():
            for kind, args in batch:  # order matters for pairing state
                if kind == "receiver":
                    code, addr, ts = args
                    await conn.execute(
                        """INSERT INTO relay_pairings (code, receiver_addr, active, last_updated)
                           VALUES ($1, $2, true, $3)
                           ON CONFLICT (code) DO UPDATE
                           SET receiver_addr = EXCLUDED.receiver_addr, active = true, last_updated = EXCLUDED.last_updated""",
                        code, addr, ts,
                    )
                elif kind == "sender":
                    code, addr, ts = args
                    await conn.execute(
                        "INSERT INTO relay_pairings (code) VALUES ($1) ON CONFLICT (code) DO NOTHING", code
                    )
                    await conn.execute(
                        "INSERT INTO relay_pairing_senders (code, addr, linked_at) VALUES ($1, $2, $3)", code, addr, ts
                    )
                elif kind == "freed":
                    await conn.execute("UPDATE relay_pairings SET active = false WHERE code = $1", args[0])
            if messages:
                await conn.executemany(
                    "INSERT INTO relay_messages (direction, ts, from_addr, size) VALUES ($1, $2, $3, $4)", messages
                )

    # ------------------------------------------------------------------ housekeeping
    async def _maintenance(self) -> None:
        while True:
            await asyncio.sleep(PRUNE_EVERY)
            if self.pool is None:
                continue
            try:
                await self.prune()
            except Exception as exc:
                log.warning("Relay prune failed: %s", exc)

    async def prune(self) -> None:
        assert self.pool is not None
        cfg = self.settings
        async with self.pool.acquire() as conn:
            if cfg.message_retention_days > 0:
                cutoff = _now() - timedelta(days=cfg.message_retention_days)
                await conn.execute("DELETE FROM relay_messages WHERE ts < $1", cutoff)
            if cfg.sender_history_per_code > 0:
                await conn.execute(
                    """DELETE FROM relay_pairing_senders s USING (
                           SELECT id, row_number() OVER (PARTITION BY code ORDER BY id DESC) AS rn
                           FROM relay_pairing_senders) r
                       WHERE s.id = r.id AND r.rn > $1""",
                    cfg.sender_history_per_code,
                )

    async def drain(self, timeout: float = 5.0) -> None:
        """Test helper: wait until queued events are written."""
        deadline = asyncio.get_running_loop().time() + timeout
        while not self.queue.empty() and asyncio.get_running_loop().time() < deadline:
            await asyncio.sleep(0.05)
        await asyncio.sleep(0.2)
