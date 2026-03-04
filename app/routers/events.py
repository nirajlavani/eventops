from datetime import time
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.event import Event
from app.models.sub_event import SubEvent
from app.schemas.event import EventCreate, EventUpdate, EventResponse

router = APIRouter()


def parse_time_string(time_str: str | None) -> time | None:
    """Parse time string to time object."""
    if not time_str:
        return None
    try:
        parts = time_str.split(":")
        return time(int(parts[0]), int(parts[1]))
    except (ValueError, IndexError):
        return None


@router.post("", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    event_data: EventCreate,
    db: AsyncSession = Depends(get_db),
) -> Event:
    """Create a new event with optional sub-events."""
    event_dict = event_data.model_dump(exclude={"sub_events"})
    event = Event(**event_dict)
    db.add(event)
    await db.flush()
    
    if event_data.sub_events:
        for idx, sub_event_data in enumerate(event_data.sub_events):
            sub_event = SubEvent(
                event_id=event.id,
                name=sub_event_data.name,
                date=sub_event_data.date,
                start_time=parse_time_string(sub_event_data.start_time),
                end_time=parse_time_string(sub_event_data.end_time),
                location=sub_event_data.location,
                description=sub_event_data.description,
                order=sub_event_data.order if sub_event_data.order else idx,
            )
            db.add(sub_event)
    
    await db.commit()
    
    result = await db.execute(
        select(Event)
        .options(selectinload(Event.sub_events))
        .where(Event.id == event.id)
    )
    return result.scalar_one()


@router.get("", response_model=List[EventResponse])
async def list_events(
    db: AsyncSession = Depends(get_db),
) -> List[Event]:
    """List all events with sub-events."""
    result = await db.execute(
        select(Event)
        .options(selectinload(Event.sub_events))
        .order_by(Event.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(
    event_id: str,
    db: AsyncSession = Depends(get_db),
) -> Event:
    """Get an event by ID with sub-events."""
    result = await db.execute(
        select(Event)
        .options(selectinload(Event.sub_events))
        .where(Event.id == event_id)
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )
    return event


@router.put("/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: str,
    event_data: EventUpdate,
    db: AsyncSession = Depends(get_db),
) -> Event:
    """Update an event."""
    result = await db.execute(
        select(Event)
        .options(selectinload(Event.sub_events))
        .where(Event.id == event_id)
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )
    
    update_data = event_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(event, field, value)
    
    await db.commit()
    await db.refresh(event)
    return event


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    event_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete an event."""
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )
    
    await db.delete(event)
    await db.commit()
