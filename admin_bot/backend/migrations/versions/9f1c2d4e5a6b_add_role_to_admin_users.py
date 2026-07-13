"""add role to admin_users

Revision ID: 9f1c2d4e5a6b
Revises: abd13290a9cc
Create Date: 2026-07-06 17:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '9f1c2d4e5a6b'
down_revision: Union[str, None] = 'abd13290a9cc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "admin_users",
        sa.Column("role", sa.Text(), nullable=False, server_default="admin"),
    )


def downgrade() -> None:
    op.drop_column("admin_users", "role")
