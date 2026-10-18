"""Relay settings, read from the environment (shared .env with the API)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass


def _int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    return int(raw) if raw else default


def _origins() -> set[str]:
    # RELAY_ALLOWED_ORIGINS, falling back to the old relay's ALLOWED_ORIGINS
    raw = os.getenv("RELAY_ALLOWED_ORIGINS") or os.getenv("ALLOWED_ORIGINS", "")
    return {o.strip() for o in raw.split(",") if o.strip()}


@dataclass(frozen=True)
class RelaySettings:
    database_url: str = ""  # empty = relay runs without persistence (like the old Mongo fallback)
    allowed_origins: set[str] = field(default_factory=set)  # empty = any origin (old default)
    max_message_bytes: int = 64 * 1024
    max_connections_per_ip: int = 10
    trusted_proxy_hops: int = 1  # how many proxies (nginx) append to X-Forwarded-For
    status_token: str = ""  # bearer token that reveals active codes on /status
    message_retention_days: int = 30
    sender_history_per_code: int = 50
    fail_tarpit_after: int = 5  # failed sender links per connection before slowing down
    fail_per_ip_10min: int = 120  # failed sender links per IP before heavy slowdown
    ws_rate_per_second: int = 200
    ws_rate_burst: int = 1000
    send_timeout: float = 10.0


def load_relay_settings() -> RelaySettings:
    return RelaySettings(
        database_url=os.getenv("DATABASE_URL", "").strip(),
        allowed_origins=_origins(),
        max_message_bytes=_int("RELAY_MAX_MESSAGE_BYTES", 64 * 1024),
        max_connections_per_ip=_int("RELAY_MAX_CONNECTIONS_PER_IP", 10),
        trusted_proxy_hops=_int("RELAY_TRUSTED_PROXY_HOPS", _int("TRUSTED_PROXY_HOPS", 1)),
        status_token=os.getenv("RELAY_STATUS_TOKEN", "").strip(),
        message_retention_days=_int("RELAY_MESSAGE_RETENTION_DAYS", 30),
        sender_history_per_code=_int("RELAY_SENDER_HISTORY_PER_CODE", 50),
        fail_tarpit_after=_int("RELAY_FAIL_TARPIT_AFTER", 5),
        fail_per_ip_10min=_int("RELAY_FAIL_PER_IP_10MIN", 120),
        ws_rate_per_second=_int("RELAY_WS_RATE_PER_SECOND", 200),
        ws_rate_burst=_int("RELAY_WS_RATE_BURST", 1000),
    )
