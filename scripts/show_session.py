"""Read a Redis session and show its user, without exposing passwords or the token."""
import argparse
from getpass import getpass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--key", help="Redis key from redis-cli --scan; otherwise prompt for the cookie UUID")
    args = parser.parse_args()

    from core.redis_client import redis_client
    from db.session import SessionLocal
    from models.user import User
    from services.auth import session_key

    key = args.key
    if key is None:
        token = getpass("Session ID из Application → Cookies (ввод скрыт): ").strip()
        if not token:
            raise SystemExit("Session ID не указан")
        key = session_key(token)
    if not key.startswith("isoarch:session:"):
        raise SystemExit("Ожидается ключ isoarch:session:<SHA-256>")
    try:
        with redis_client.pipeline(transaction=True) as pipeline:
            value, ttl = pipeline.get(key).ttl(key).execute()
        print(f"Redis key: {key}")
        print(f"Redis GET (user_id): {value}")
        print(f"Redis TTL: {ttl} seconds")
        if value is None:
            raise SystemExit("Сессия отсутствует, истекла или была отозвана. Войдите снова через Swagger.")
        with SessionLocal() as db:
            user = db.get(User, int(value))
            if user is None:
                raise SystemExit("Пользователь сессии отсутствует в PostgreSQL")
            print(f"PostgreSQL user: id={user.id}, username={user.username}, full_name={user.full_name}")
    finally:
        redis_client.close()


if __name__ == "__main__":
    main()
