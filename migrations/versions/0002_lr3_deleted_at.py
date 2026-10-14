"""Add an explicit soft-delete timestamp without removing existing data."""
from alembic import op
import sqlalchemy as sa

revision = "0002_lr3_deleted_at"
down_revision = "0001_lr3"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    columns = {c["name"] for c in sa.inspect(bind).get_columns("isotopic_signatures")}
    if "deleted_at" not in columns:
        op.add_column("isotopic_signatures", sa.Column("deleted_at", sa.DateTime(), nullable=True))
    records = sa.table("isotopic_signatures", sa.column("status"), sa.column("deleted_at"),
                       sa.column("completed_at"), sa.column("created_at"))
    bind.execute(records.update().where(
        records.c.status == "deleted", records.c.deleted_at.is_(None)
    ).values(deleted_at=sa.func.coalesce(records.c.completed_at, records.c.created_at)))


def downgrade():
    raise RuntimeError("Destructive downgrades are unsupported; restore a backup")
