from datetime import date, time, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class CalendarEventBase(BaseModel):
    """Base schema for calendar event data."""

    title: str
    event_date: date
    end_date: Optional[date] = None
    event_time: Optional[time] = None
    all_day: bool = True
    location: Optional[str] = None
    notes: Optional[str] = None


class CalendarEventCreate(CalendarEventBase):
    """Schema for creating a calendar event."""
    pass


class CalendarEventUpdate(BaseModel):
    """Schema for updating a calendar event."""

    title: Optional[str] = None
    event_date: Optional[date] = None
    end_date: Optional[date] = None
    event_time: Optional[time] = None
    all_day: Optional[bool] = None
    location: Optional[str] = None
    notes: Optional[str] = None


class CalendarEventResponse(CalendarEventBase):
    """Schema for calendar event response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    event_id: str
    created_at: datetime
    updated_at: datetime
