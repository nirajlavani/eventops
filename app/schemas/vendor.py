from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class VendorBase(BaseModel):
    """Base schema for vendor data."""
    
    name: str
    category: Optional[str] = None
    contact_info: Optional[str] = None
    notes: Optional[str] = None


class VendorCreate(VendorBase):
    """Schema for creating a vendor."""
    pass


class VendorUpdate(BaseModel):
    """Schema for updating a vendor."""
    
    name: Optional[str] = None
    category: Optional[str] = None
    contact_info: Optional[str] = None
    notes: Optional[str] = None


class VendorResponse(VendorBase):
    """Schema for vendor response."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    event_id: str
    created_at: datetime
    updated_at: datetime
