from datetime import date, time
from decimal import Decimal
from typing import Optional, Union, Literal
from enum import Enum

from pydantic import BaseModel, Field


class IntentType(str, Enum):
    """Intent types for NL capture."""
    PAYMENT = "payment"
    TASK = "task"
    CALENDAR_EVENT = "calendar_event"
    VENDOR = "vendor"
    SUB_EVENT_UPDATE = "sub_event_update"
    EVENT_UPDATE = "event_update"
    UNKNOWN = "unknown"


class PaymentData(BaseModel):
    """Extracted payment data."""
    
    vendor_name: Optional[str] = None
    amount_paid: Optional[Decimal] = None
    remaining_balance: Optional[Decimal] = None
    payment_date: Optional[date] = None
    due_date: Optional[date] = None
    method: Optional[str] = None
    notes: Optional[str] = None


class TaskData(BaseModel):
    """Extracted task data."""
    
    title: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[date] = None
    priority: Optional[Literal["low", "medium", "high"]] = "medium"


class CalendarEventData(BaseModel):
    """Extracted calendar event data."""
    
    title: Optional[str] = None
    event_date: Optional[date] = None
    event_time: Optional[time] = None
    location: Optional[str] = None
    notes: Optional[str] = None


class VendorData(BaseModel):
    """Extracted vendor data."""
    
    name: Optional[str] = None
    category: Optional[str] = None
    contact_info: Optional[str] = None
    notes: Optional[str] = None


class SubEventUpdateData(BaseModel):
    """Extracted sub-event update data."""
    
    action: Literal["add", "update", "cancel", "reschedule"]
    sub_event_name: Optional[str] = None
    new_name: Optional[str] = None
    new_date: Optional[date] = None
    new_start_time: Optional[time] = None
    new_end_time: Optional[time] = None
    new_location: Optional[str] = None
    description: Optional[str] = None


class EventUpdateData(BaseModel):
    """Extracted event update data."""
    
    name: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    location: Optional[str] = None
    location_city: Optional[str] = None
    description: Optional[str] = None


class UnknownData(BaseModel):
    """Empty data for unknown intent."""
    pass


class CaptureRequest(BaseModel):
    """Request schema for NL capture extraction."""
    
    text: str = Field(..., min_length=1, max_length=5000)


class CaptureResponse(BaseModel):
    """Response schema for NL capture extraction."""
    
    intent: IntentType
    confidence: float = Field(..., ge=0.0, le=1.0)
    data: Union[PaymentData, TaskData, CalendarEventData, VendorData, SubEventUpdateData, EventUpdateData, UnknownData, dict]
    missing_fields: list[str] = Field(default_factory=list)
    needs_confirmation: bool = True
    log_id: str


class ConfirmRequest(BaseModel):
    """Request schema for confirming extracted data."""
    
    log_id: str
    intent: IntentType
    data: Union[PaymentData, TaskData, CalendarEventData, VendorData, SubEventUpdateData, EventUpdateData]


class ConfirmResponse(BaseModel):
    """Response schema for confirmation."""
    
    success: bool
    message: str
    created_id: Optional[str] = None
