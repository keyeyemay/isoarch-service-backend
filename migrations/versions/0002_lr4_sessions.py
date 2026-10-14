"""Add persistent sessions without changing LR3 users or services."""
from alembic import op
import sqlalchemy as sa

revision = "0002_lr4_sessions"
down_revision = "0001_lr3"
branch_labels = None
depends_on = None


def upgrade():
    # 0001 uses current metadata on a fresh DB, so the table may already exist.
    if "auth_sessions" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table("auth_sessions",
            sa.Column("token_hash", sa.String(64), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False))
        op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
        op.create_index("ix_auth_sessions_expires_at", "auth_sessions", ["expires_at"])


def downgrade():
    op.drop_table("auth_sessions")
