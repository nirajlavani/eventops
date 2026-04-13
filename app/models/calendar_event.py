import uuid
from datetime import datetime, date, time
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Text, Date, Time, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.event import Event


class CalendarEvent(Base):
    """User-created calendar event associated with a wedding/event."""

    __tablename__ = "calendar_events"

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
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    event_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    all_day: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    location: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    event: Mapped["Event"] = relationship("Event", back_populates="calendar_events")
