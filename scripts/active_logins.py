"""Show every active Redis session via the server-side Lua script."""
from datetime import datetime, timedelta


def main():
    from core.config import SESSION_TTL_SECONDS
    from core.redis_client import redis_client
    from db.session import SessionLocal
    from models.user import User
    from services.auth import active_sessions

    try:
        sessions = active_sessions()
        if not sessions:
            print("Активных сессий нет")
            return
        print(f"Активных сессий: {len(sessions)}")

        by_login: dict[str, list[dict]] = {}
        for session in sessions:
            by_login.setdefault(session["login"], []).append(session)

        now = datetime.now()
        with SessionLocal() as db:
            for login, items in by_login.items():
                user = db.get(User, items[0]["user_id"])
                print(f"\n{login} (id={items[0]['user_id']}) — сессий: {len(items)}")
                if user is not None and (user.full_name or user.email):
                    print(f"  {user.full_name or ''}{', ' if user.full_name and user.email else ''}{user.email or ''}")
                for session in items:
                    ttl = session["ttl"]
                    login_at = now - timedelta(seconds=SESSION_TTL_SECONDS - ttl)
                    hours, minutes = divmod(ttl // 60, 60)
                    print(f"  • {session['key']}")
                    print(f"    вход {login_at:%d.%m %H:%M} · осталось {hours}ч {minutes:02d}м (TTL {ttl} с)")
    finally:
        redis_client.close()


if __name__ == "__main__":
    main()
