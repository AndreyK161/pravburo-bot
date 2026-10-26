"""add scheduled_steps and tg_users.last_activity_at

Revision ID: a9d3e5f7b2c4
Revises: f1b8c2d4e6a7
Create Date: 2026-10-06
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'a9d3e5f7b2c4'
down_revision: Union[str, None] = 'f1b8c2d4e6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Когда юзер в последний раз что-то нажал/написал боту: по нему решаем, отменять
    # ли напоминание (если после старта цепочки была активность — не отправляем).
    op.execute("ALTER TABLE tg_users ADD COLUMN IF NOT EXISTS last_activity_at TIMESTAMPTZ")
    # Отложенные шаги сценария (блоки "delay"): переживают перезапуск бота,
    # потому что лежат в БД, а не в памяти процесса.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS scheduled_steps (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            chat_id BIGINT NOT NULL,
            next_block_id TEXT NOT NULL,
            fire_at TIMESTAMPTZ NOT NULL,
            chain_started_at TIMESTAMPTZ NOT NULL,
            always BOOLEAN NOT NULL DEFAULT false,
            status TEXT NOT NULL DEFAULT 'pending',
            attempts INT NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_scheduled_steps_due ON scheduled_steps (status, fire_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_scheduled_steps_user ON scheduled_steps (user_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS scheduled_steps")
    op.execute("ALTER TABLE tg_users DROP COLUMN IF EXISTS last_activity_at")
