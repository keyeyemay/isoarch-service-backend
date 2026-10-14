"""Password verification and Redis sessions with automatic expiration."""
import hashlib
import hmac
import secrets
import uuid
from fastapi import HTTPException
from redis.exceptions import RedisError
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


def session_key(token: str) -> str:
    return "isoarch:session:" + token_digest(token)


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
        value = redis_client.get(session_key(token))
    except RedisError as exc:
        raise HTTPException(503, "Session storage is unavailable") from exc
    return int(value) if value is not None else None


def create_session(user_id: int, previous_token: str | None = None) -> str:
    token = str(uuid.uuid4())
    try:
        # Redis MULTI/EXEC rotates the old token and creates the new TTL atomically.
        with redis_client.pipeline(transaction=True) as transaction:
            if previous_token:
                transaction.delete(session_key(previous_token))
            transaction.set(session_key(token), str(user_id), ex=SESSION_TTL_SECONDS)
            transaction.execute()
    except RedisError as exc:
        raise HTTPException(503, "Session storage is unavailable") from exc
    return token
