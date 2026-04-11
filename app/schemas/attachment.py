from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class AttachmentResponse(BaseModel):
    """Schema for attachment response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    event_id: str
    vendor_id: Optional[str] = None
    payment_id: Optional[str] = None
    filename: str
    original_filename: str
    content_type: Optional[str] = None
    file_size: Optional[int] = None
    category: Optional[str] = None
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    vendor_name: Optional[str] = None
    payment_description: Optional[str] = None


class AttachmentUpdate(BaseModel):
    """Schema for updating attachment metadata."""

    description: Optional[str] = Field(None, max_length=1000)
    category: Optional[str] = Field(None, max_length=50)
    vendor_id: Optional[str] = None
    payment_id: Optional[str] = None
