"""Capture modes, explicit proposal states, message links and retry receipts."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "6a8e21b4d390"
down_revision = "4f3b9c6d1a2e"
branch_labels = None
depends_on = None


def upgrade():
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE financial_event_status ADD VALUE IF NOT EXISTS 'AWAITING_CONFIRMATION'")
        op.execute("ALTER TYPE financial_event_status ADD VALUE IF NOT EXISTS 'REJECTED'")
    op.add_column("users", sa.Column("review_transactions", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("users", sa.Column("timezone", sa.String(64), nullable=False, server_default="UTC"))
    op.add_column("financial_events", sa.Column("assistant_message_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("messages.id", ondelete="SET NULL"), nullable=True))
    op.add_column("financial_events", sa.Column("revision", sa.Integer(), nullable=False, server_default="1"))
    op.create_table("capture_receipts",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("request_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("fingerprint", sa.Text(), nullable=False),
        sa.Column("response", postgresql.JSONB(), nullable=False))
    op.execute("""UPDATE financial_events SET status = 'AWAITING_CONFIRMATION'
        WHERE status = 'NEEDS_CLARIFICATION' AND COALESCE(jsonb_array_length(missing_fields), 0) = 0
        AND jsonb_array_length(COALESCE(extracted_data->'transactions', '[]'::jsonb)) > 0""")
    op.execute("UPDATE financial_events SET status = 'REJECTED' WHERE status = 'FAILED' AND error = 'Rejected by user'")
    # Link legacy proposals by their event interval, including clarification turns.
    op.execute("""UPDATE financial_events e SET assistant_message_id = (
        SELECT m.id FROM messages m WHERE m.conversation_id = e.conversation_id
        AND m.role = 'ASSISTANT' AND m.created_at >= e.created_at
        AND m.created_at < COALESCE((SELECT MIN(n.created_at) FROM financial_events n
            WHERE n.conversation_id = e.conversation_id AND n.created_at > e.created_at), 'infinity')
        ORDER BY m.created_at DESC LIMIT 1)""")


def downgrade():
    op.execute("UPDATE financial_events SET status = 'NEEDS_CLARIFICATION' WHERE status = 'AWAITING_CONFIRMATION'")
    op.execute("UPDATE financial_events SET status = 'FAILED' WHERE status = 'REJECTED'")
    op.drop_table("capture_receipts")
    op.drop_column("financial_events", "revision")
    op.drop_column("financial_events", "assistant_message_id")
    op.drop_column("users", "timezone")
    op.drop_column("users", "review_transactions")
