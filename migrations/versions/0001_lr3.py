"""Create LR3 schema or preserve and upgrade the LR2 database."""
from alembic import op
import sqlalchemy as sa
from db.base import Base
import models

revision = "0001_lr3"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    tables = sa.inspect(bind).get_table_names()
    if "isotopic_signatures" not in tables:
        Base.metadata.create_all(bind)
        return
    for table in ("users", "signature_likes"):
        cols = {c["name"] for c in sa.inspect(bind).get_columns(table)}
        with op.batch_alter_table(table) as batch:
            if "created_at" not in cols:
                batch.add_column(sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()))
            if table == "users" and "password" not in cols:
                # Legacy users had no credentials. Login remains a stub in LR3.
                batch.add_column(sa.Column("password", sa.String(255), nullable=False, server_default="legacy-account"))
    indexes = {i["name"] for i in sa.inspect(bind).get_indexes("isotopic_signatures")}
    if "uq_user_single_draft" in indexes:
        op.drop_index("uq_user_single_draft", table_name="isotopic_signatures")
    cols = {c["name"] for c in sa.inspect(bind).get_columns("isotopic_signatures")}
    with op.batch_alter_table("isotopic_signatures") as batch:
        for old, new, kind in [("image_url", "image_file", sa.String(500)), ("video_url", "video_file", sa.String(500)), ("formation_date", "formed_at", sa.DateTime())]:
            if new not in cols:
                if old in cols:
                    batch.alter_column(old, new_column_name=new, existing_type=kind)
                else:
                    batch.add_column(sa.Column(new, kind, nullable=True))
        if "moderator_id" not in cols:
            batch.add_column(sa.Column("moderator_id", sa.Integer(), nullable=True))
            batch.create_foreign_key("fk_signature_moderator", "users", ["moderator_id"], ["id"], ondelete="RESTRICT")
        if "completed_at" not in cols:
            batch.add_column(sa.Column("completed_at", sa.DateTime(), nullable=True))
    signatures = sa.table("isotopic_signatures", sa.column("status"), sa.column("formed_at"), sa.column("image_file"), sa.column("video_file"))
    for old, new in [("черновик", "draft"), ("опубликован", "published"), ("удален", "deleted"), ("удалён", "deleted")]:
        bind.execute(signatures.update().where(signatures.c.status == old).values(status=new))
    bind.execute(signatures.update().where(signatures.c.status == "draft").values(formed_at=None))
    # Legacy URLs pointing to this bucket become object names; preserve other values.
    from core.config import MINIO_ENDPOINT, MEDIA_BUCKET
    prefix = MINIO_ENDPOINT.rstrip("/") + "/" + MEDIA_BUCKET + "/"
    for field in ("image_file", "video_file"):
        column = getattr(signatures.c, field)
        rows = bind.execute(sa.select(column).where(column.startswith(prefix))).scalars().all()
        for value in rows:
            bind.execute(signatures.update().where(column == value).values({field: value[len(prefix):]}))
    checks = {c["name"] for c in sa.inspect(bind).get_check_constraints("isotopic_signatures")}
    if "ck_signature_status" not in checks:
        with op.batch_alter_table("isotopic_signatures") as batch:
            batch.create_check_constraint("ck_signature_status", "status IN ('draft', 'published', 'deleted')")
    op.create_index("uq_user_single_draft", "isotopic_signatures", ["creator_id"], unique=True,
                    postgresql_where=sa.text("status = 'draft'"), sqlite_where=sa.text("status = 'draft'"))


def downgrade():
    raise RuntimeError("A destructive downgrade is intentionally unsupported; restore a database backup")
