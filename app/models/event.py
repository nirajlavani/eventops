import uuid
from datetime import datetime, date
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import String, Text, Date
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.vendor import Vendor
    from app.models.payment import Payment
    from app.models.task import Task
    from app.models.calendar_event import CalendarEvent
    from app.models.attachment import Attachment
    from app.models.ai_log import AILog
    from app.models.sub_event import SubEvent


class Event(Base):
    """Top-level event entity (wedding, conference, etc.)."""
    
    __tablename__ = "events"
    
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    event_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    location_city: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
    
    vendors: Mapped[List["Vendor"]] = relationship(
        "Vendor",
        back_populates="event",
        cascade="all, delete-orphan",
    )
    payments: Mapped[List["Payment"]] = relationship(
        "Payment",
        back_populates="event",
        cascade="all, delete-orphan",
    )
    tasks: Mapped[List["Task"]] = relationship(
        "Task",
        back_populates="event",
        cascade="all, delete-orphan",
    )
    calendar_events: Mapped[List["CalendarEvent"]] = relationship(
        "CalendarEvent",
        back_populates="event",
        cascade="all, delete-orphan",
    )
    attachments: Mapped[List["Attachment"]] = relationship(
        "Attachment",
        back_populates="event",
        cascade="all, delete-orphan",
    )
    ai_logs: Mapped[List["AILog"]] = relationship(
        "AILog",
        back_populates="event",
        cascade="all, delete-orphan",
    )
    sub_events: Mapped[List["SubEvent"]] = relationship(
        "SubEvent",
        back_populates="event",
        cascade="all, delete-orphan",
        order_by="SubEvent.order, SubEvent.date",
    )
