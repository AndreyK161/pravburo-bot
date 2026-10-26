"""add quiz_answers to tg_users

Revision ID: f1b8c2d4e6a7
Revises: a7c3f9e2b4d1
Create Date: 2026-10-05
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'f1b8c2d4e6a7'
down_revision: Union[str, None] = 'a7c3f9e2b4d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Ответы на вопросы квиза: {"q1": 0, "q2": 2, ...} — вопрос -> баллы за выбранный ответ.
    # Сумму считаем при подведении итогов, а не храним: ответ можно перезаписать при перепрохождении.
    op.execute("ALTER TABLE tg_users ADD COLUMN IF NOT EXISTS quiz_answers JSONB NOT NULL DEFAULT '{}'::jsonb")


def downgrade() -> None:
    op.execute("ALTER TABLE tg_users DROP COLUMN IF EXISTS quiz_answers")
