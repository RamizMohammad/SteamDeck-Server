"""Runtime configuration, read once from environment variables (and .env)."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

try:  # .env support is optional, the container gets real env vars
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass

log = logging.getLogger("linkium.config")

# The secret the old Node server silently fell back to. Never accept it.
_INSECURE_DEFAULT_SECRET = "default-secret-change-this"

_DEFAULT_CORS = "https://connection.desksync.space,https://desksync.space,http://localhost:5173"


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


def _list(name: str, default: str) -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    database_url: str
    jwt_secret: str
    db_pool_size: int = 10
    port: int = 8002
    cors_origins: list[str] = field(default_factory=lambda: _DEFAULT_CORS.split(","))
    public_ws_url: str = "wss://api.server.desksync.space/ws"
    jwt_expires_days: int = 30
    bcrypt_rounds: int = 10
    max_body_bytes: int = 100 * 1024  # same as express.json() default
    activity_log_max: int = 1000  # 0 = unbounded (old behaviour)
    preserve_user_programs: bool = False  # True = keep hand-added programs on receiver sync
    auth_rate_per_minute: int = 20  # per client IP on POST /api/auth
    auth_fail_per_15min: int = 10  # failed passwords per email
    ws_require_auth: bool = False
    ws_enforce_origin: bool = False
    ws_rate_per_second: int = 200
    ws_rate_burst: int = 1000
    ws_max_code_length: int = 128
    trusted_proxy_hops: int = 1  # proxies that append to X-Forwarded-For (nginx = 1)


def load_settings() -> Settings:
    dsn = os.getenv("DATABASE_URL", "").strip()
    if not dsn:
        raise RuntimeError("DATABASE_URL is not set (postgresql://user:pass@host:5432/db).")

    secret = os.getenv("JWT_SECRET", "").strip()
    if not secret or secret == _INSECURE_DEFAULT_SECRET:
        raise RuntimeError(
            "JWT_SECRET is missing or set to the old insecure default. "
            "Set a long random value (e.g. `openssl rand -hex 32`)."
        )
    if len(secret) < 32:
        log.warning("JWT_SECRET is shorter than 32 characters; consider a longer one.")

    return Settings(
        database_url=dsn,
        jwt_secret=secret,
        db_pool_size=_int("DB_POOL_SIZE", 10),
        port=_int("PORT", 8002),
        cors_origins=_list("CORS_ORIGINS", _DEFAULT_CORS),
        public_ws_url=os.getenv("PUBLIC_WS_URL", "wss://api.server.desksync.space/ws"),
        jwt_expires_days=_int("JWT_EXPIRES_DAYS", 30),
        bcrypt_rounds=_int("BCRYPT_ROUNDS", 10),
        max_body_bytes=_int("MAX_BODY_BYTES", 100 * 1024),
        activity_log_max=_int("ACTIVITY_LOG_MAX", 1000),
        preserve_user_programs=_bool("PRESERVE_USER_PROGRAMS", False),
        auth_rate_per_minute=_int("AUTH_RATE_PER_MINUTE", 20),
        auth_fail_per_15min=_int("AUTH_FAIL_PER_15MIN", 10),
        ws_require_auth=_bool("WS_REQUIRE_AUTH", False),
        ws_enforce_origin=_bool("WS_ENFORCE_ORIGIN", False),
        ws_rate_per_second=_int("WS_RATE_PER_SECOND", 200),
        ws_rate_burst=_int("WS_RATE_BURST", 1000),
        ws_max_code_length=_int("WS_MAX_CODE_LENGTH", 128),
        trusted_proxy_hops=_int("TRUSTED_PROXY_HOPS", 1),
    )
