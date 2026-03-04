from typing import List, Optional

from pydantic import BaseModel


class PlanningRequest(BaseModel):
    """Request schema for AI planning."""
    
    query: Optional[str] = "What should I focus on this week?"


class PriorityItem(BaseModel):
    """A prioritized item from the planning assistant."""
    
    category: str
    title: str
    reason: str
    urgency: str
    due_date: Optional[str] = None


class PlanningResponse(BaseModel):
    """Response schema for AI planning."""
    
    summary: str
    priority_items: List[PriorityItem]
    recommendations: List[str]
