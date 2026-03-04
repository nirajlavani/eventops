from datetime import date, datetime
from typing import Optional
from enum import Enum

from pydantic import BaseModel, ConfigDict


class TaskStatus(str, Enum):
    """Task status enumeration."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class TaskPriority(str, Enum):
    """Task priority enumeration."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TaskBase(BaseModel):
    """Base schema for task data."""
    
    title: str
    description: Optional[str] = None
    due_date: Optional[date] = None
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.MEDIUM


class TaskCreate(TaskBase):
    """Schema for creating a task."""
    pass


class TaskUpdate(BaseModel):
    """Schema for updating a task."""
    
    title: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[date] = None
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None


class TaskResponse(TaskBase):
    """Schema for task response."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    event_id: str
    created_at: datetime
    updated_at: datetime
