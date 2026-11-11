"""List active Redis sessions via the server-side Lua script.

With --cookie the script asks for the session_id cookie value from the browser
(hidden input), computes SHA-256 and marks the matching Redis session.
"""
import argparse
from getpass import getpass


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cookie", action="store_true",
                        help="ask for the browser cookie session_id and mark its session")
    args = parser.parse_args()

    from core.redis_client import redis_client
    from services.auth import active_sessions, session_key

    browser_key = None
    if args.cookie:
        token = getpass("session_id из DevTools → Application → Cookies (ввод скрыт): ").strip()
        browser_key = session_key(token) if token else None

    try:
        sessions = active_sessions()
        if not sessions:
            print("Активных сессий нет")
            return
        print(f"{'ЛОГИН':<20} {'ID':>4}  {'КЛЮЧ СЕССИИ В REDIS':<32} {'СОЗДАНА (UTC)':<26} {'TTL, с':>7}")
        for s in sessions:
            mark = "  ← этот браузер" if s["session_key"] == browser_key else ""
            short_key = s["session_key"][:28] + "…"
            print(f"{s['login']:<20} {s['user_id']:>4}  {short_key:<32} {s['created_at']:<26} {s['ttl']:>7}{mark}")
        counts: dict[str, int] = {}
        for s in sessions:
            counts[s["login"]] = counts.get(s["login"], 0) + 1
        print("\nИтого: " + ", ".join(f"{login} — {n}" for login, n in sorted(counts.items())))
        if browser_key and browser_key not in {s["session_key"] for s in sessions}:
            print("Сессия этого браузера в Redis не найдена (истекла, отозвана или cookie неверна)")
    finally:
        redis_client.close()


if __name__ == "__main__":
    main()
