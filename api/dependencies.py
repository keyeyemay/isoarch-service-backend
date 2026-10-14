from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import APIKeyCookie
from sqlalchemy.orm import Session
from db.session import get_db
from models.user import User
from services.auth import session_user_id

session_cookie = APIKeyCookie(name="session_id", auto_error=False, scheme_name="SessionCookie",
    description="Сессия из POST /auth/login. Cookie: session_id=<UUID>. Swagger отправляет HttpOnly cookie после входа автоматически; вручную используйте Postman Headers.")


def get_session_token(request: Request) -> str | None:
    """Accept both cookie spellings in Lab4; the browser uses session_id."""
    return request.cookies.get("session_id") or request.cookies.get("session-id")


def get_optional_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    """Public reading with optional personalization from the cookie."""
    user_id = session_user_id(get_session_token(request))
    return db.get(User, user_id) if user_id is not None else None


def get_current_user(request: Request, user: User | None = Depends(get_optional_user),
                     token: str | None = Security(session_cookie)) -> User:
    """Resolve the user through the session cookie; never accept a client-supplied user ID."""
    if user is None:
        raise HTTPException(401, "Authentication required")
    return user
