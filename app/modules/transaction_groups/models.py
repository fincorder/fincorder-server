import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class TransactionGroupStatus(str, Enum):
    PENDING = "pending"
    POSTED = "posted"
    REVERSED = "reversed"


class TransactionGroup(Base):
    __tablename__ = "transaction_groups"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    financial_event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("financial_events.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[TransactionGroupStatus] = mapped_column(
        SQLEnum(TransactionGroupStatus, name="transaction_group_status"),
        nullable=False,
        default=TransactionGroupStatus.PENDING,
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
    
    financial_event = relationship(
        "FinancialEvent",
        back_populates="transaction_groups",
    )