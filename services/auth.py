"""Password verification and Redis sessions with automatic expiration."""
import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timezone
from pathlib import Path
from fastapi import HTTPException
from redis.exceptions import RedisError, ResponseError
from core.redis_client import redis_client
from core.config import SESSION_TTL_SECONDS


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return f"scrypt${salt}${digest}"


# Use the same expensive computation for unknown usernames and legacy accounts.
DUMMY_PASSWORD = hash_password("unusable-" + secrets.token_hex(32))


def verify_password(password: str, encoded: str) -> bool:
    valid_format = encoded.startswith("scrypt$")
    try:
        _, salt, expected = (encoded if valid_format else DUMMY_PASSWORD).split("$")
        digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
        return hmac.compare_digest(digest, expected) and valid_format
    except (ValueError, TypeError):
        return False


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


SESSION_PREFIX = "isoarch:session:"
# A session is a Redis HASH {user_id, username, created_at} with a TTL. The login is kept
# inside the session itself, so the Lua script reads everything from the session keys.
ACTIVE_LOGINS_LUA = Path(__file__).with_name("active_logins.lua").read_text(encoding="utf-8")


def session_key(token: str) -> str:
    return SESSION_PREFIX + token_digest(token)


def revoke_session(token: str | None):
    if token:
        try:
            redis_client.delete(session_key(token))
        except RedisError as exc:
            raise HTTPException(503, "Session storage is unavailable") from exc


def session_user_id(token: str | None) -> int | None:
    if not token or len(token) > 128:
        return None
    try:
        value = redis_client.hget(session_key(token), "user_id")
    except ResponseError:
        return None  # key of another type (e.g. an old string session): not a valid session
    except RedisError as exc:
        raise HTTPException(503, "Session storage is unavailable") from exc
    return int(value) if value is not None else None


def create_session(user_id: int, username: str, previous_token: str | None = None) -> str:
    token = str(uuid.uuid4())
    try:
        # Redis MULTI/EXEC rotates the old token and creates the new TTL atomically.
        with redis_client.pipeline(transaction=True) as transaction:
            if previous_token:
                transaction.delete(session_key(previous_token))
            key = session_key(token)
            transaction.delete(key)
            transaction.hset(key, mapping={
                "user_id": str(user_id),
                "username": username,
                "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            })
            transaction.expire(key, SESSION_TTL_SECONDS)
            transaction.execute()
    except RedisError as exc:
        raise HTTPException(503, "Session storage is unavailable") from exc
    return token


def active_sessions() -> list[dict]:
    """Run the Lua script: every active session with its login, key, creation time and TTL."""
    try:
        reply = redis_client.eval(ACTIVE_LOGINS_LUA, 0, SESSION_PREFIX + "*")
    except RedisError as exc:
        raise HTTPException(503, "Session storage is unavailable") from exc
    sessions = []
    for entry in reply:
        fields = [item.decode() if isinstance(item, bytes) else item for item in entry]
        session = dict(zip(fields[::2], fields[1::2]))
        session["user_id"] = int(session["user_id"])
        session["ttl"] = int(session["ttl"])
        sessions.append(session)
    return sessions


def active_logins() -> list[tuple[str, int]]:
    """Logins with active sessions and the number of their sessions (from the Lua script)."""
    counts: dict[str, int] = {}
    for session in active_sessions():
        counts[session["login"]] = counts.get(session["login"], 0) + 1
    return sorted(counts.items())
