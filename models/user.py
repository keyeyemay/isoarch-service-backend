from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import relationship

from db.base import Base


class User(Base):
    __tablename__ = "users"

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=True)
    email = Column(String(255), unique=True, nullable=True)
    password = Column(String(255), nullable=False)

    signatures = relationship(
        "IsotopicSignature",
        back_populates="creator",
        foreign_keys="[IsotopicSignature.creator_id]",
        passive_deletes="all",  
    )
    likes = relationship(
        "SignatureLike",
        back_populates="user",
        passive_deletes="all",  
    )


