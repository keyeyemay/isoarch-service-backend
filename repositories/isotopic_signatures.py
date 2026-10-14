from sqlalchemy.orm import Session, selectinload
from models import IsotopicSignature


def published_query(db: Session):
    return db.query(IsotopicSignature).filter(
        IsotopicSignature.status == "published", IsotopicSignature.deleted_at.is_(None))


def first_published(db: Session):
    return published_query(db).order_by(IsotopicSignature.id.asc()).first()


def by_id(db: Session, signature_id: int):
    return db.query(IsotopicSignature).filter(
        IsotopicSignature.id == signature_id, IsotopicSignature.status != "deleted",
        IsotopicSignature.deleted_at.is_(None)).first()


def published_by_id(db: Session, signature_id: int):
    return published_query(db).filter(IsotopicSignature.id == signature_id).first()


def next_published(db: Session, signature_id: int):
    return (published_query(db).filter(IsotopicSignature.id > signature_id)
            .order_by(IsotopicSignature.id.asc()).first()) or first_published(db)


def draft_for_user(db: Session, user_id: int):
    return db.query(IsotopicSignature).filter_by(creator_id=user_id, status="draft", deleted_at=None).first()


def search_published(db: Session, c13_max: float | None = None, filter_value: str = ""):
    query = published_query(db).options(selectinload(IsotopicSignature.likes))
    if c13_max is not None:
        query = query.filter(IsotopicSignature.delta_c13 <= c13_max)
    if filter_value:
        query = query.filter(IsotopicSignature.title.ilike(f"%{filter_value}%"))
    return query.order_by(IsotopicSignature.id.asc()).all()
