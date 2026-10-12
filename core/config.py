import os

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://isoarch_user:isoarch_password@localhost:5432/isoarch_lr2_db")
MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "http://localhost:9000")
MEDIA_BUCKET = os.environ.get("MEDIA_BUCKET", "isoarchservice")
CURRENT_USER_ID = 1
DEFAULT_IMAGE_URL = "/static/images/default_signature.png"
DEFAULT_VIDEO_URL = "/static/videos/default_signature.mp4"
