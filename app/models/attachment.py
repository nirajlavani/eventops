import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Text, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.event import Event
    from app.models.vendor import Vendor
    from app.models.payment import Payment


class Attachment(Base):
    """File attachment linked to an event, optionally to a vendor or payment."""

    __tablename__ = "attachments"

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
    payment_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("payments.id", ondelete="SET NULL"),
        nullable=True,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    content_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    event: Mapped["Event"] = relationship("Event", back_populates="attachments")
    vendor: Mapped[Optional["Vendor"]] = relationship("Vendor", back_populates="attachments")
    payment: Mapped[Optional["Payment"]] = relationship("Payment", back_populates="attachments")
