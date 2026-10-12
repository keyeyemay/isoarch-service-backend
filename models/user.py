from datetime import datetime
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from db.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=True)
    email = Column(String(255), unique=True, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    signatures = relationship(
        "IsotopicSignature",
        back_populates="creator",
        passive_deletes="all",  # Запрет каскадного удаления
    )
    likes = relationship(
        "SignatureLike",
        back_populates="user",
        passive_deletes="all",  # Запрет каскадного удаления
    )


