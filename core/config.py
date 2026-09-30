import os

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://isoarch_user:isoarch_password@localhost:5432/isoarch_db",
)
MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "http://localhost:9000")
MEDIA_BUCKET = os.environ.get("MEDIA_BUCKET", "isoarchservice")
CURRENT_USER_ID = 1
DEFAULT_IMAGE_URL = "/static/images/default_signature.png"
DEFAULT_VIDEO_URL = "/static/videos/default_signature.mp4"

MINIO_ROOT_USER = os.environ.get("MINIO_ROOT_USER", "root")
MINIO_ROOT_PASSWORD = os.environ.get("MINIO_ROOT_PASSWORD", "rootpassword")
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_VIDEO_BYTES = 64 * 1024 * 1024
MAX_VIDEO_SECONDS = 60
