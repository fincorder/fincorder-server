"""Store profile-image object keys on users."""

from alembic import op
import sqlalchemy as sa


revision = "79bd18012a4c"
down_revision = "6a8e21b4d390"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("avatar_key", sa.String(length=512), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "avatar_key")
