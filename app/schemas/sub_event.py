from datetime import date, time, datetime
from typing import Optional, List

from pydantic import BaseModel, ConfigDict, Field


class SubEventBase(BaseModel):
    """Base schema for sub-event data."""
    
    name: str = Field(..., min_length=1, max_length=255)
    date: date
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    location: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = None
    order: int = 0


class SubEventCreate(SubEventBase):
    """Schema for creating a sub-event."""
    pass


class SubEventUpdate(BaseModel):
    """Schema for updating a sub-event."""
    
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    date: Optional[date] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    location: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = None
    order: Optional[int] = None


class SubEventResponse(SubEventBase):
    """Schema for sub-event response."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    event_id: str
    created_at: datetime
    updated_at: datetime


class SubEventBulkCreate(BaseModel):
    """Schema for bulk creating sub-events."""
    
    sub_events: List[SubEventCreate] = Field(..., min_length=1)


class SubEventReorder(BaseModel):
    """Schema for reordering sub-events."""
    
    sub_event_ids: List[str] = Field(..., min_length=1)
