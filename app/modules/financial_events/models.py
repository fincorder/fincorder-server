import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class FinancialEventStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    NEEDS_CLARIFICATION = "needs_clarification"
    COMPLETED = "completed"
    FAILED = "failed"


class FinancialEvent(Base):
    __tablename__ = "financial_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[FinancialEventStatus] = mapped_column(
        SQLEnum(FinancialEventStatus, name="financial_event_status"),
        nullable=False,
        default=FinancialEventStatus.PENDING,
    )
    raw_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    extracted_data: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    missing_fields: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    conversation = relationship(
        "Conversation",
        back_populates="financial_events",
    )

    source_message = relationship(
        "Message",
        back_populates="financial_events",
    )

    transaction_groups = relationship(
        "TransactionGroup",
        back_populates="financial_event",
        cascade="all, delete-orphan",
    )