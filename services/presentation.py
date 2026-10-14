from sqlalchemy import select, exists
from sqlalchemy.orm import object_session
from models import SignatureLike
from core.config import MINIO_ENDPOINT, MEDIA_BUCKET, DEFAULT_IMAGE_URL, DEFAULT_VIDEO_URL
from urllib.parse import quote


def build_media_url(key, default_type="image"):
    if not key:
        return DEFAULT_VIDEO_URL if default_type == "video" else DEFAULT_IMAGE_URL
    base = MINIO_ENDPOINT.rstrip("/")
    if "://" not in base:
        base = "http://" + base
    return f"{base}/{MEDIA_BUCKET}/{quote(str(key), safe='/')}"


def isotopic_signature_display(signature, user_id):
    fields = ["id", "title", "description", "status", "image_file", "video_file", "delta_n15", "delta_c13",
              "created_at", "creator_id", "moderator_id", "formed_at", "completed_at", "deleted_at"]
    result = {field: getattr(signature, field) for field in fields}
    result.update(image_url=build_media_url(signature.image_file),
                  video_url=build_media_url(signature.video_file, "video"),
                  is_creator=int(signature.creator_id == user_id),
                  is_liked=int(object_session(signature).scalar(select(exists().where(
                      SignatureLike.signature_id == signature.id, SignatureLike.user_id == user_id)))),
                  likes_count=len(signature.likes))
    for field in ("delta_n15", "delta_c13"):
        result[field + "_display"] = f"{result[field]:.1f} ‰" if result[field] is not None else "—"
    return result
