import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Text, Date, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.event import Event
    from app.models.vendor import Vendor


class Payment(Base):
    """Payment record for an event."""
    
    __tablename__ = "payments"
    
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    event_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
    )
    vendor_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("vendors.id", ondelete="SET NULL"),
        nullable=True,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    paid_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    
    event: Mapped["Event"] = relationship("Event", back_populates="payments")
    vendor: Mapped[Optional["Vendor"]] = relationship("Vendor", back_populates="payments")
