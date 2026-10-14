"""Shared Redis connection pool for server-side sessions."""
from redis import Redis
from core.config import REDIS_URL

redis_client = Redis.from_url(REDIS_URL, decode_responses=True,
                              socket_connect_timeout=3, socket_timeout=3)


def init_redis():
    redis_client.ping()
