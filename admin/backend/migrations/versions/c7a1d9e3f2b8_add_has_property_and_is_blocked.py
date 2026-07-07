"""add has_property and is_blocked to users

Revision ID: c7a1d9e3f2b8
Revises: b2e7f1a3c9d0
Create Date: 2026-07-07
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'c7a1d9e3f2b8'
down_revision: Union[str, None] = 'b2e7f1a3c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # TEXT, а не BOOLEAN: хранит 'yes'/'no' тем же механизмом save_user_field,
    # что и остальные поля из сценария (name/phone/region) — без спецкейсов под тип.
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS has_property TEXT")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_blocked BOOLEAN NOT NULL DEFAULT false")


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS has_property")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS is_blocked")
