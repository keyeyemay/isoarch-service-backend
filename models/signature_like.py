from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import relationship

from db.base import Base


class SignatureLike(Base):
    __tablename__ = "signature_likes"

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    id = Column(Integer, primary_key=True, index=True)  # Первичный ключ
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    signature_id = Column(
        Integer,
        ForeignKey("isotopic_signatures.id", ondelete="RESTRICT"),
        nullable=False,
    ) 

    user = relationship("User", back_populates="likes")
    signature = relationship("IsotopicSignature", back_populates="likes")

    __table_args__ = (
        UniqueConstraint("user_id", "signature_id", name="uq_user_signature_like"),
    )
