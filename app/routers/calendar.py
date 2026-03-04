from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.event import Event
from app.models.calendar_event import CalendarEvent
from app.schemas.calendar_event import (
    CalendarEventCreate,
    CalendarEventUpdate,
    CalendarEventResponse,
)

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


@router.post("", response_model=CalendarEventResponse, status_code=status.HTTP_201_CREATED)
async def create_calendar_event(
    event_id: str,
    calendar_event_data: CalendarEventCreate,
    db: AsyncSession = Depends(get_db),
) -> CalendarEvent:
    """Create a new calendar event for an event."""
    await get_event_or_404(event_id, db)
    
    calendar_event = CalendarEvent(event_id=event_id, **calendar_event_data.model_dump())
    db.add(calendar_event)
    await db.commit()
    await db.refresh(calendar_event)
    return calendar_event


@router.get("", response_model=List[CalendarEventResponse])
async def list_calendar_events(
    event_id: str,
    db: AsyncSession = Depends(get_db),
) -> List[CalendarEvent]:
    """List all calendar events for an event."""
    await get_event_or_404(event_id, db)
    
    result = await db.execute(
        select(CalendarEvent)
        .where(CalendarEvent.event_id == event_id)
        .order_by(CalendarEvent.event_date.asc())
    )
    return list(result.scalars().all())


@router.get("/{calendar_event_id}", response_model=CalendarEventResponse)
async def get_calendar_event(
    event_id: str,
    calendar_event_id: str,
    db: AsyncSession = Depends(get_db),
) -> CalendarEvent:
    """Get a calendar event by ID."""
    await get_event_or_404(event_id, db)
    
    result = await db.execute(
        select(CalendarEvent).where(
            CalendarEvent.id == calendar_event_id,
            CalendarEvent.event_id == event_id,
        )
    )
    calendar_event = result.scalar_one_or_none()
    if not calendar_event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calendar event not found",
        )
    return calendar_event


@router.put("/{calendar_event_id}", response_model=CalendarEventResponse)
async def update_calendar_event(
    event_id: str,
    calendar_event_id: str,
    calendar_event_data: CalendarEventUpdate,
    db: AsyncSession = Depends(get_db),
) -> CalendarEvent:
    """Update a calendar event."""
    await get_event_or_404(event_id, db)
    
    result = await db.execute(
        select(CalendarEvent).where(
            CalendarEvent.id == calendar_event_id,
            CalendarEvent.event_id == event_id,
        )
    )
    calendar_event = result.scalar_one_or_none()
    if not calendar_event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calendar event not found",
        )
    
    update_data = calendar_event_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(calendar_event, field, value)
    
    await db.commit()
    await db.refresh(calendar_event)
    return calendar_event


@router.delete("/{calendar_event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_calendar_event(
    event_id: str,
    calendar_event_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a calendar event."""
    await get_event_or_404(event_id, db)
    
    result = await db.execute(
        select(CalendarEvent).where(
            CalendarEvent.id == calendar_event_id,
            CalendarEvent.event_id == event_id,
        )
    )
    calendar_event = result.scalar_one_or_none()
    if not calendar_event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calendar event not found",
        )
    
    await db.delete(calendar_event)
    await db.commit()
