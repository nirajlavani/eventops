from datetime import date
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel


class UpcomingPayment(BaseModel):
    """Upcoming payment summary."""
    
    id: str
    vendor_name: Optional[str]
    amount: Decimal
    due_date: date
    notes: Optional[str]


class OpenTask(BaseModel):
    """Open task summary."""
    
    id: str
    title: str
    due_date: Optional[date]
    priority: str
    status: str


class UpcomingCalendarEvent(BaseModel):
    """Upcoming calendar event summary."""
    
    id: str
    title: str
    event_date: date
    event_time: Optional[str]
    location: Optional[str]


class VendorSummary(BaseModel):
    """Vendor summary statistics."""
    
    total_vendors: int
    by_category: dict


class FinancialSummary(BaseModel):
    """Financial summary statistics."""
    
    total_paid: Decimal
    total_upcoming: Decimal
    by_vendor: dict


class DashboardResponse(BaseModel):
    """Dashboard summary response."""
    
    event_id: str
    event_name: str
    upcoming_payments: List[UpcomingPayment]
    open_tasks: List[OpenTask]
    upcoming_events: List[UpcomingCalendarEvent]
    vendor_summary: VendorSummary
    financial_summary: FinancialSummary
