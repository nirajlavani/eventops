from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class EventBase(BaseModel):
    """Base schema for event data."""
    
    name: str
    event_type: Optional[str] = None
    event_date: Optional[date] = None
    location: Optional[str] = None
    description: Optional[str] = None


class EventCreate(EventBase):
    """Schema for creating an event."""
    pass


class EventUpdate(BaseModel):
    """Schema for updating an event."""
    
    name: Optional[str] = None
    event_type: Optional[str] = None
    event_date: Optional[date] = None
    location: Optional[str] = None
    description: Optional[str] = None


class EventResponse(EventBase):
    """Schema for event response."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    created_at: datetime
    updated_at: datetime
