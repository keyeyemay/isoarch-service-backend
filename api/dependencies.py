from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from core.config import CURRENT_USER_ID
from db.session import get_db
from models.user import User


def get_current_user(db: Session = Depends(get_db)) -> User:
    
    user = db.get(User, CURRENT_USER_ID)
    if user is None:
        raise HTTPException(503, "Current user is not initialized")
    return user
