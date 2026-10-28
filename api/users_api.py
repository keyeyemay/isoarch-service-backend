from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from api.schemas import UserRegister, UserLogin, UserResponse
from api.dependencies import get_current_user, get_session_token
from core.config import SESSION_COOKIE_SECURE, SESSION_TTL_SECONDS
from db.session import get_db
from models.user import User
from services.auth import hash_password, verify_password, create_session, revoke_session

router = APIRouter(tags=["Авторизация"])


@router.post("/auth/register", response_model=UserResponse, status_code=201,
             summary="Регистрация", responses={409: {"description": "Логин или email занят"}})
def register_user(user_data: UserRegister, db: Session = Depends(get_db)):
    """Создать пользователя. Пароль сохраняется как scrypt-хеш; вход выполняется отдельно."""
    user = User(username=user_data.username, password=hash_password(user_data.password),
                full_name=user_data.full_name, email=user_data.email)
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Username or email already registered") from exc
    db.refresh(user)
    return user


@router.post("/auth/login", response_model=UserResponse, summary="Вход и создание cookie-сессии",
             responses={401: {"description": "Неверный логин или пароль"}})
def login_user(data: UserLogin, request: Request, response: Response, db: Session = Depends(get_db)):
    """Проверить пароль, заменить текущую сессию и установить HttpOnly cookie session_id."""
    user = db.query(User).filter_by(username=data.username).first()
    if not verify_password(data.password, user.password if user else "") or user is None:
        raise HTTPException(401, "Invalid username or password")
    token = create_session(user.id, user.username, get_session_token(request))
    response.delete_cookie(key="session-id", path="/")
    response.set_cookie(key="session_id", value=token, max_age=SESSION_TTL_SECONDS,
                        httponly=True, secure=SESSION_COOKIE_SECURE, samesite="lax", path="/")
    response.headers["Cache-Control"] = "no-store"
    return user


@router.post("/auth/logout", status_code=204, summary="Выход и удаление сессии")
def logout_user(request: Request):
    """Удалить серверную сессию и cookie. Повторный выход безопасен."""
    revoke_session(get_session_token(request))
    response = Response(status_code=204)
    response.delete_cookie(key="session_id", path="/", httponly=True,
                           secure=SESSION_COOKIE_SECURE, samesite="lax")
    response.delete_cookie(key="session-id", path="/")
    return response


@router.get("/auth/me", response_model=UserResponse, summary="Текущий пользователь",
            responses={401: {"description": "Нет действующей сессии"}})
def current_user(user: User = Depends(get_current_user)):
    """Данные пользователя текущей сессии, без пароля и токена."""
    return user


# Compatible URLs from LR3, with the same authentication and permissions.
router.add_api_route("/api/users/register", register_user, methods=["POST"], response_model=UserResponse, status_code=201, include_in_schema=False)
router.add_api_route("/api/users/login", login_user, methods=["POST"], response_model=UserResponse, include_in_schema=False)
router.add_api_route("/api/users/logout", logout_user, methods=["POST"], status_code=204, include_in_schema=False)
