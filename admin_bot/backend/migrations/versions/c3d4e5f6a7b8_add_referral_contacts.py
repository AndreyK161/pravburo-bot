"""Store referral contacts separately from partner profiles."""
from alembic import op

revision = "c3d4e5f6a7b8"
down_revision = "a9d3e5f7b2c4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE referral_contacts (
            id BIGSERIAL PRIMARY KEY,
            partner_telegram_id BIGINT NOT NULL,
            partner_name TEXT NOT NULL,
            partner_username TEXT,
            contact_name TEXT NOT NULL,
            contact_phone TEXT NOT NULL,
            chat_id BIGINT NOT NULL,
            message_id BIGINT NOT NULL,
            marker TEXT NOT NULL DEFAULT 'partner_first_contact',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            bitrix_lead_id BIGINT,
            bitrix_status TEXT NOT NULL DEFAULT 'pending',
            UNIQUE (chat_id, message_id)
        )
    """)
    op.execute("CREATE INDEX ix_referral_contacts_partner ON referral_contacts (partner_telegram_id)")


def downgrade() -> None:
    op.execute("DROP TABLE referral_contacts")
