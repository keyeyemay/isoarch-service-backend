from typing import Optional
from core.config import MINIO_ENDPOINT, MEDIA_BUCKET
from models import IsotopicSignature

def build_media_url(key: Optional[str], default_type: str = "image") -> str:
    """Формирование полного URL медиафайла с фоллбэком на SSR-ресурсы по умолчанию."""
    if not key or not str(key).strip():
        if default_type == "video":
            return "/static/videos/default_signature.mp4"
        return "/static/images/default_signature.png"

    key_str = str(key).strip()
    if key_str.startswith("http://") or key_str.startswith("https://") or key_str.startswith("/static/"):
        return key_str

    return f"{MINIO_ENDPOINT}/{MEDIA_BUCKET}/{key_str}"


def isotopic_signature_display(signature: IsotopicSignature) -> dict:
    """Преобразование сущности ORM в словарь с форматированными полями отображения."""
    image_url = build_media_url(signature.image_url, default_type="image")
    video_url = build_media_url(signature.video_url, default_type="video")

    n15_val = signature.delta_n15 if signature.delta_n15 is not None else 0.0
    c13_val = signature.delta_c13 if signature.delta_c13 is not None else 0.0


    return {
        "id": signature.id,
        "title": signature.title,
        "description": signature.description or "",
        "status": signature.status,
        "image_url": image_url,
        "video_url": video_url,
        "delta_n15": signature.delta_n15,
        "delta_c13": signature.delta_c13,
        "delta_n15_display": f"{n15_val:.1f} ‰",
        "delta_c13_display": f"{c13_val:.1f} ‰",
        "likes_count": len(signature.likes) if signature.likes is not None else 0,
        "creator_id": signature.creator_id,
    }


