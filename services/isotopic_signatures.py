from datetime import datetime
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from models import IsotopicSignature, SignatureLike
from repositories import isotopic_signatures as repository
from core import minio_client as storage
from services.media import read_media


def list_services(db, c13_max=None, filter_value=""):
    return repository.search_published(db, c13_max, filter_value)


def get_feed(db, signature_id=None, next=False):
    if signature_id is None:
        record = repository.first_published(db)
    else:
        record = repository.by_id(db, signature_id)
        if record is None or record.status != "published":
            raise HTTPException(404, "Service not found")
        if next:
            record = repository.next_published(db, signature_id)
    if record is None:
        raise HTTPException(404, "No published services")
    return record


def get_draft(db, user_id):
    return repository.draft_for_user(db, user_id)


def create_draft(db: Session, user_id: int, title: str, image, video):
    title = title.strip()
    if not title or len(title) > 255:
        raise HTTPException(422, "Title must contain 1–255 characters")
    if get_draft(db, user_id):
        raise HTTPException(409, "Draft already exists")
    # Validate both files before writing either one.
    image_data, image_type = read_media(image, "image")
    video_data, video_type = read_media(video, "video")
    uploaded = []
    try:
        uploaded.append(storage.upload_file_to_minio(image_data, image.filename, image_type))
        uploaded.append(storage.upload_file_to_minio(video_data, video.filename, video_type))
        draft = IsotopicSignature(title=title, status="draft", image_file=uploaded[0],
                                  video_file=uploaded[1], creator_id=user_id)
        db.add(draft)
        db.commit()
    except Exception as exc:
        db.rollback()
        for key in uploaded:
            storage.remove_file_from_minio(key)
        if isinstance(exc, storage.StorageError):
            raise HTTPException(503, "Media storage is unavailable") from exc
        if isinstance(exc, IntegrityError):
            raise HTTPException(409, "Draft already exists") from exc
        raise
    db.refresh(draft)
    return draft


def owned_service(db, signature_id, user_id):
    record = repository.by_id(db, signature_id)
    if record is None or record.status == "deleted":
        raise HTTPException(404, "Service not found")
    if record.creator_id != user_id:
        raise HTTPException(403, "Only the creator can change this service")
    return record


def publish_draft(db, signature_id, user_id, data):
    draft = owned_service(db, signature_id, user_id)
    if draft.status != "draft":
        raise HTTPException(409, "Only drafts can be published")
    draft.description = data.description
    draft.delta_n15 = data.delta_n15
    draft.delta_c13 = data.delta_c13
    draft.status = "published"
    draft.formed_at = datetime.utcnow()
    db.commit()
    db.refresh(draft)
    return draft


def delete_service(db, signature_id, user_id):
    record = owned_service(db, signature_id, user_id)
    record.status = "deleted"
    record.completed_at = datetime.utcnow()
    db.commit()


def toggle_like(db, signature_id, user_id, value):
    record = get_feed(db, signature_id)
    existing = db.query(SignatureLike).filter_by(user_id=user_id, signature_id=signature_id).first()
    if value == 1 and existing is None:
        db.add(SignatureLike(user_id=user_id, signature_id=signature_id))
    elif value == 0 and existing is not None:
        db.delete(existing)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # A concurrent request may have created the same unique like.
        if value != 1 or not db.query(SignatureLike).filter_by(user_id=user_id, signature_id=signature_id).first():
            raise
    db.expire(record, ["likes"])
    return {"like": value, "likes_count": len(record.likes)}
