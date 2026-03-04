from datetime import date, datetime, time
from typing import Optional, List, TYPE_CHECKING, Union, Any

from pydantic import BaseModel, ConfigDict, Field, field_serializer

if TYPE_CHECKING:
    from app.schemas.sub_event import SubEventResponse, SubEventCreate


class EventBase(BaseModel):
    """Base schema for event data."""
    
    name: str
    event_type: Optional[str] = None
    event_date: Optional[date] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    location: Optional[str] = None
    location_city: Optional[str] = None
    description: Optional[str] = None


class SubEventCreateInline(BaseModel):
    """Inline sub-event for event creation."""
    
    name: str = Field(..., min_length=1, max_length=255)
    date: date
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    order: int = 0


class EventCreate(EventBase):
    """Schema for creating an event."""
    
    sub_events: Optional[List[SubEventCreateInline]] = None


class EventUpdate(BaseModel):
    """Schema for updating an event."""
    
    name: Optional[str] = None
    event_type: Optional[str] = None
    event_date: Optional[date] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    location: Optional[str] = None
    location_city: Optional[str] = None
    description: Optional[str] = None


class SubEventResponseInline(BaseModel):
    """Inline sub-event response for event responses."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    name: str
    date: date
    start_time: Any = None
    end_time: Any = None
    location: Optional[str] = None
    description: Optional[str] = None
    order: int
    
    @field_serializer('start_time', 'end_time')
    def serialize_time(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, time):
            return value.strftime('%H:%M')
        return str(value) if value else None


class EventResponse(EventBase):
    """Schema for event response."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    created_at: datetime
    updated_at: datetime
    sub_events: List[SubEventResponseInline] = Field(default_factory=list)
