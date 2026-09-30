import io
import json
import logging
import uuid
from urllib.parse import urlsplit
from minio import Minio
from urllib3 import PoolManager, Timeout
from core.config import MEDIA_BUCKET, MINIO_ENDPOINT, MINIO_ROOT_USER, MINIO_ROOT_PASSWORD

log = logging.getLogger(__name__)
endpoint = urlsplit(MINIO_ENDPOINT if "://" in MINIO_ENDPOINT else "http://" + MINIO_ENDPOINT)
minio_client = Minio(endpoint.netloc, access_key=MINIO_ROOT_USER,
                     secret_key=MINIO_ROOT_PASSWORD, secure=endpoint.scheme == "https",
                     http_client=PoolManager(timeout=Timeout(connect=3, read=10), retries=0))


class StorageError(Exception):
    pass


def init_minio():
    try:
        if not minio_client.bucket_exists(MEDIA_BUCKET):
            minio_client.make_bucket(MEDIA_BUCKET)
        # Existing buckets also need a read policy for browser playback.
        minio_client.set_bucket_policy(MEDIA_BUCKET, json.dumps({
            "Version": "2012-10-17", "Statement": [{"Effect": "Allow",
            "Principal": {"AWS": ["*"]}, "Action": ["s3:GetObject"],
            "Resource": [f"arn:aws:s3:::{MEDIA_BUCKET}/*"]}]}))
    except Exception as exc:
        raise StorageError("MinIO initialization failed") from exc


def upload_file_to_minio(file_data: bytes, filename: str, content_type: str) -> str:
    # Extension comes from the validated MIME type, never from an arbitrary filename.
    extensions = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp", "video/mp4": "mp4"}
    key = f"{uuid.uuid4().hex}.{extensions[content_type]}"
    try:
        minio_client.put_object(MEDIA_BUCKET, key, io.BytesIO(file_data), len(file_data), content_type=content_type)
    except Exception as exc:
        # Also attempt cleanup if storage accepted the object but the reply was lost.
        remove_file_from_minio(key)
        raise StorageError("Media upload failed") from exc
    return key


def remove_file_from_minio(key: str):
    try:
        minio_client.remove_object(MEDIA_BUCKET, key)
    except Exception:
        log.exception("Cannot clean up MinIO object %s", key)
