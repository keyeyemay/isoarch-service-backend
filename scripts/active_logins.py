"""List logins with active Redis sessions via the server-side Lua script."""


def main():
    from core.redis_client import redis_client
    from services.auth import active_logins

    try:
        logins = active_logins()
        if not logins:
            print("Активных сессий нет")
        for login, count in logins:
            print(f"{login}: сессий {count}")
    finally:
        redis_client.close()


if __name__ == "__main__":
    main()
