"""Legacy intermediate LR4 table; active sessions now live exclusively in Redis."""
from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from db.base import Base


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    token_hash = Column(String(64), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
