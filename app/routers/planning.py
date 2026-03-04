from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.event import Event
from app.services.planning import PlanningService, get_planning_service
from app.schemas.planning import PlanningRequest, PlanningResponse, PriorityItem

router = APIRouter()


async def get_event_or_404(event_id: str, db: AsyncSession) -> Event:
    """Get an event by ID or raise 404."""
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )
    return event


@router.post("/focus", response_model=PlanningResponse)
async def get_focus_recommendations(
    event_id: str,
    request: PlanningRequest = None,
    db: AsyncSession = Depends(get_db),
    planning_service: PlanningService = Depends(get_planning_service),
) -> PlanningResponse:
    """
    Get AI-powered planning recommendations.
    
    Analyzes the event's tasks, payments, and calendar events to provide
    prioritized recommendations on what to focus on.
    
    Example queries:
    - "What should I focus on this week?"
    - "What payments are due soon?"
    - "What's most urgent right now?"
    """
    await get_event_or_404(event_id, db)
    
    if request is None:
        request = PlanningRequest()
    
    result = await planning_service.get_focus_recommendations(
        event_id=event_id,
        query=request.query,
        db=db,
    )
    
    priority_items = [
        PriorityItem(
            category=item.get("category", "task"),
            title=item.get("title", ""),
            reason=item.get("reason", ""),
            urgency=item.get("urgency", "upcoming"),
            due_date=item.get("due_date"),
        )
        for item in result.get("priority_items", [])
    ]
    
    return PlanningResponse(
        summary=result.get("summary", ""),
        priority_items=priority_items,
        recommendations=result.get("recommendations", []),
    )
