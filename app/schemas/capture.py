from datetime import date, time
from decimal import Decimal
from typing import Optional, Union, Literal, Any
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
    QUERY = "query"
    CONVERSATION = "conversation"
    UNKNOWN = "unknown"


class ActionType(str, Enum):
    """Action types for extraction."""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


class ResponseMode(str, Enum):
    """Response mode indicating how the UI should render the response."""
    CONFIRM = "confirm"      # Confirming an action before execution
    CLARIFY = "clarify"      # Asking for clarification or more info
    ANSWER = "answer"        # Answering a question with data
    EXECUTE = "execute"      # Action executed successfully
    ERROR = "error"          # Something went wrong


class PaymentData(BaseModel):
    """Extracted payment data."""
    
    vendor_name: Optional[str] = None
    amount_paid: Optional[Decimal] = None
    remaining_balance: Optional[Decimal] = None
    payment_date: Optional[date] = None
    due_date: Optional[date] = None
    method: Optional[str] = None
    notes: Optional[str] = None


class TaskItem(BaseModel):
    """Single task item for bulk operations."""
    title: str
    description: Optional[str] = None
    due_date: Optional[date] = None
    priority: Optional[Literal["low", "medium", "high"]] = "medium"


class TaskData(BaseModel):
    """Extracted task data - supports single or bulk tasks."""
    
    model_config = {"extra": "allow"}
    
    title: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[date] = None
    priority: Optional[Literal["low", "medium", "high"]] = "medium"
    items: Optional[list[dict]] = None  # For bulk task creation


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


class QueryData(BaseModel):
    """Extracted query data."""
    
    query_type: Literal["list", "aggregate", "search", "status"] = "list"
    target: Literal["payments", "tasks", "vendors", "calendar_events", "all"] = "all"
    filters: Optional[dict] = None
    sort_by: Optional[str] = None
    sort_order: Optional[Literal["asc", "desc"]] = "desc"
    limit: Optional[int] = None


class QueryResults(BaseModel):
    """Results from a query."""
    
    query_type: str
    target: str
    results: dict
    natural_response: str


class ConversationData(BaseModel):
    """Data for conversational responses."""
    
    model_config = {"extra": "allow"}
    
    topic: Optional[str] = None
    answer: Optional[Any] = None
    related_record_id: Optional[str] = None


class UnknownData(BaseModel):
    """Empty data for unknown intent."""
    pass


class ConversationMessage(BaseModel):
    """A single message in conversation history."""
    role: str  # "user" or "assistant"
    content: str


class CaptureRequest(BaseModel):
    """Request schema for NL capture extraction."""
    
    text: str = Field(..., min_length=1, max_length=5000)
    conversation_history: Optional[list[ConversationMessage]] = None


class CaptureResponse(BaseModel):
    """Response schema for NL capture extraction."""
    
    intent: IntentType
    action: ActionType = ActionType.CREATE
    confidence: float = Field(..., ge=0.0, le=1.0)
    data: Union[PaymentData, TaskData, CalendarEventData, VendorData, SubEventUpdateData, EventUpdateData, QueryData, ConversationData, UnknownData, dict]
    missing_fields: list[str] = Field(default_factory=list)
    needs_confirmation: bool = True
    reference_id: Optional[str] = None
    follow_up_question: Optional[str] = None
    assistant_message: Optional[str] = None
    response_mode: ResponseMode = ResponseMode.CONFIRM
    referenced_records: Optional[list[str]] = None  # IDs of records used in the response
    query_results: Optional[QueryResults] = None
    log_id: str


class ConfirmRequest(BaseModel):
    """Request schema for confirming extracted data."""
    
    log_id: str
    intent: IntentType
    action: ActionType = ActionType.CREATE
    reference_id: Optional[str] = None
    data: Union[PaymentData, TaskData, CalendarEventData, VendorData, SubEventUpdateData, EventUpdateData]


class ConfirmResponse(BaseModel):
    """Response schema for confirmation."""
    
    success: bool
    message: str
    created_id: Optional[str] = None
