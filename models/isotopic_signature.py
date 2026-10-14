from datetime import datetime
from sqlalchemy import Column, DateTime, Float, ForeignKey, CheckConstraint, Index, Integer, String, Text
from sqlalchemy.orm import relationship

from db.base import Base


class IsotopicSignature(Base):
    __tablename__ = "isotopic_signatures"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(
        String(50), nullable=False, default="draft"
    )
    image_file = Column(String(500), nullable=True)
    video_file = Column(String(500), nullable=True)

    
    delta_n15 = Column(Float, nullable=True)
    delta_c13 = Column(Float, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    creator_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    moderator_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    formed_at = Column(
        DateTime, nullable=True
    )
    deleted_at = Column(DateTime, nullable=True)

    completed_at = Column(
        DateTime, nullable=True
    )

    creator = relationship("User", back_populates="signatures", foreign_keys=[creator_id])
    moderator = relationship("User", foreign_keys=[moderator_id])
    likes = relationship(
        "SignatureLike",
        back_populates="signature",
        passive_deletes="all",
    )

    __table_args__ = (
        CheckConstraint("status IN ('draft', 'published', 'deleted')", name="ck_signature_status"),
        Index(
            "uq_user_single_draft",
            "creator_id",
            unique=True,
            postgresql_where=(status == "draft"),
            sqlite_where=(status == "draft"),
        ),
    )
