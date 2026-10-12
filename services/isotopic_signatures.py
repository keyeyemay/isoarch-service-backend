from datetime import datetime, timezone
from fastapi import HTTPException
from core.config import CURRENT_USER_ID, DEFAULT_IMAGE_URL, DEFAULT_VIDEO_URL
from models import IsotopicSignature
from repositories import isotopic_signatures as repository
from services.presentation import isotopic_signature_display


def feed_entry_id(db):
    record = repository.first_published(db)
    return record.id if record else None


def catalog_context(db, c13_max, filter_value):
    value = c13_max.strip() if c13_max else filter_value.strip()
    records, active_c13 = repository.search_published(db, value)
    return {"isotopic_signatures": [isotopic_signature_display(s) for s in records],
            "c13_max": f"{active_c13:.1f}", "is_filtered": bool(value), "feed_entry_id": feed_entry_id(db)}


def feed_context(db, isotopic_signature_id):
    requested = repository.by_id(db, isotopic_signature_id)
    if requested is not None and requested.status == "удален":
        return "deleted.html", {"isotopic_signature_id": requested.id, "title": requested.title,
                                "feed_entry_id": feed_entry_id(db)}, 404
    first = repository.first_published(db)
    if first is None:
        raise HTTPException(404, "Нет опубликованных изотопных сигнатур")
    current = requested if requested is not None and requested.status == "опубликован" else first
    following = repository.next_published(db, current.id)
    return "feed.html", {"isotopic_signature": isotopic_signature_display(current),
                         "next_isotopic_signature_id": following.id if following else first.id,
                         "feed_entry_id": first.id}, 200


def draft_context(db):
    draft = repository.draft_for_user(db, CURRENT_USER_ID)
    return {"draft": isotopic_signature_display(draft) if draft else None, "has_draft": draft is not None,
            "default_image_url": DEFAULT_IMAGE_URL, "default_video_url": DEFAULT_VIDEO_URL,
            "feed_entry_id": feed_entry_id(db)}


def create_draft(db, title):
    if repository.draft_for_user(db, CURRENT_USER_ID) is None:
        db.add(IsotopicSignature(title=title.strip(), description="", status="черновик",
                                image_url=None, video_url=None, delta_n15=None, delta_c13=None,
                                creator_id=CURRENT_USER_ID))
        db.commit()


def publish_draft(db, description, delta_n15, delta_c13):
    draft = repository.draft_for_user(db, CURRENT_USER_ID)
    if draft is None:
        raise HTTPException(400, "У вас нет активного черновика для публикации")
    draft.description = description.strip()
    draft.delta_n15 = delta_n15
    draft.delta_c13 = delta_c13
    draft.formation_date = datetime.now(timezone.utc).replace(tzinfo=None)
    draft.status = "опубликован"
    db.commit()
    return draft.id
