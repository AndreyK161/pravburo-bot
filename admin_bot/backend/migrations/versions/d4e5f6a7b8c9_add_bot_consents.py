"""Persist consent independently for each bot and scenario version."""
from alembic import op

revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE bot_consents (
            user_id BIGINT NOT NULL,
            bot_id BIGINT NOT NULL,
            version TEXT NOT NULL,
            pending_block TEXT NOT NULL,
            accepted_at TIMESTAMPTZ,
            PRIMARY KEY (user_id, bot_id, version)
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE bot_consents")
