from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


class PaymentBase(BaseModel):
    """Base schema for payment data."""
    
    vendor_id: Optional[str] = None
    amount: Decimal
    paid_date: Optional[date] = None
    due_date: Optional[date] = None
    method: Optional[str] = None
    notes: Optional[str] = None


class PaymentCreate(PaymentBase):
    """Schema for creating a payment."""
    pass


class PaymentUpdate(BaseModel):
    """Schema for updating a payment."""
    
    vendor_id: Optional[str] = None
    amount: Optional[Decimal] = None
    paid_date: Optional[date] = None
    due_date: Optional[date] = None
    method: Optional[str] = None
    notes: Optional[str] = None


class PaymentResponse(PaymentBase):
    """Schema for payment response."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    event_id: str
    created_at: datetime
