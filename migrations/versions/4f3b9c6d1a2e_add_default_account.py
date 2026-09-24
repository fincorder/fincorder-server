"""add default account flag

Revision ID: 4f3b9c6d1a2e
Revises: 292f067eb2f8
Create Date: 2026-09-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4f3b9c6d1a2e"
down_revision: Union[str, Sequence[str], None] = "292f067eb2f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("accounts", sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.execute(
        sa.text(
            """
            UPDATE accounts
            SET is_default = TRUE
            WHERE name = 'Spending Account'
              AND deleted_at IS NULL
              AND NOT EXISTS (
                  SELECT 1 FROM accounts selected
                  WHERE selected.user_id = accounts.user_id
                    AND selected.is_default = TRUE
                    AND selected.deleted_at IS NULL
              )
            """
        )
    )
    op.alter_column("accounts", "is_default", server_default=None)


def downgrade() -> None:
    op.drop_column("accounts", "is_default")
