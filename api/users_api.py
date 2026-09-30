import hashlib
import secrets
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from api.schemas import UserRegister, UserResponse
from db.session import get_db
from models.user import User

router = APIRouter(prefix="/api/users", tags=["Users API"])


def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return f"scrypt${salt}${digest}"


@router.post("/register", response_model=UserResponse, status_code=201)
def register_user(user_data: UserRegister, db: Session = Depends(get_db)):
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


@router.post("/login")
def login_user():
    return {"message": "Authentication stub for LR4", "authenticated": False}


@router.post("/logout")
def logout_user():
    return {"message": "Logout stub for LR4"}
