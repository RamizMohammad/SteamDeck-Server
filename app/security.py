"""Password hashing and JWTs, wire-compatible with bcryptjs + jsonwebtoken.

* Hashes made by bcryptjs ($2a$/$2b$) verify here, and hashes made here verify in bcryptjs.
* Tokens issued by the old server stay valid as long as JWT_SECRET is the same.
"""

from __future__ import annotations

import time
from typing import Any

import anyio
import bcrypt
import jwt
from bson import ObjectId
from bson.errors import InvalidId

from .config import Settings

_settings: Settings | None = None


def init(settings: Settings) -> None:
    global _settings
    _settings = settings


def _cfg() -> Settings:
    if _settings is None:
        raise RuntimeError("security.init() not called")
    return _settings


def _pw_bytes(password: str) -> bytes:
    # bcryptjs silently uses only the first 72 UTF-8 bytes; python-bcrypt >= 5 raises instead.
    return password.encode("utf-8")[:72]


async def hash_password(password: str) -> str:
    rounds = _cfg().bcrypt_rounds

    def _hash() -> str:
        return bcrypt.hashpw(_pw_bytes(password), bcrypt.gensalt(rounds)).decode("ascii")

    return await anyio.to_thread.run_sync(_hash)  # keep the event loop free


async def verify_password(password: str, password_hash: Any) -> bool:
    if not isinstance(password_hash, str) or not password_hash:
        return False

    def _check() -> bool:
        try:
            return bcrypt.checkpw(_pw_bytes(password), password_hash.encode("ascii"))
        except ValueError:
            return False

    return await anyio.to_thread.run_sync(_check)


def generate_token(user_id: str) -> str:
    cfg = _cfg()
    iat = int(time.time())
    payload = {"userId": user_id, "iat": iat, "exp": iat + cfg.jwt_expires_days * 86400}
    return jwt.encode(payload, cfg.jwt_secret, algorithm="HS256")


def verify_token(token: str) -> str | None:
    """Return the userId if the token is valid, else None."""
    try:
        payload = jwt.decode(token, _cfg().jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    user_id = payload.get("userId")
    if not isinstance(user_id, str):
        return None
    try:
        ObjectId(user_id)
    except (InvalidId, TypeError):
        return None
    return user_id


def user_id_from_header(authorization: str | None) -> tuple[str | None, str | None]:
    """Mirror of the old authMiddleware. Returns (userId, error_message)."""
    if not authorization or not authorization.startswith("Bearer "):
        return None, "Unauthorized: No token provided"
    user_id = verify_token(authorization[7:])
    if user_id is None:
        return None, "Unauthorized: Invalid token"
    return user_id, None
