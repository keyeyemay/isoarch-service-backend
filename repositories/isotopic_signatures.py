from db.raw_queries import execute_raw_update_query
from models import IsotopicSignature


def published_query(db):
    return db.query(IsotopicSignature).filter(IsotopicSignature.status == "опубликован")


def first_published(db):
    return published_query(db).order_by(IsotopicSignature.id.asc()).first()


def by_id(db, isotopic_signature_id):
    return db.query(IsotopicSignature).filter(IsotopicSignature.id == isotopic_signature_id).first()


def next_published(db, isotopic_signature_id):
    return published_query(db).filter(IsotopicSignature.id > isotopic_signature_id).order_by(IsotopicSignature.id.asc()).first()


def draft_for_user(db, user_id):
    return db.query(IsotopicSignature).filter(IsotopicSignature.creator_id == user_id, IsotopicSignature.status == "черновик").first()


def search_published(db, value):
    query = published_query(db)
    active_c13 = -10.0
    if value:
        try:
            active_c13 = float(value)
            query = query.filter(IsotopicSignature.delta_c13 <= active_c13)
        except ValueError:
            query = query.filter(IsotopicSignature.title.ilike(f"%{value}%"))
    return query.order_by(IsotopicSignature.id.asc()).all(), active_c13


def soft_delete(isotopic_signature_id):
    execute_raw_update_query("UPDATE isotopic_signatures SET status = 'удален' WHERE id = %s", (isotopic_signature_id,))
