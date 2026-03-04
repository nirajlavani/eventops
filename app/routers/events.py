from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.event import Event
from app.schemas.event import EventCreate, EventUpdate, EventResponse

router = APIRouter()


@router.post("", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    event_data: EventCreate,
    db: AsyncSession = Depends(get_db),
) -> Event:
    """Create a new event."""
    event = Event(**event_data.model_dump())
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event


@router.get("", response_model=List[EventResponse])
async def list_events(
    db: AsyncSession = Depends(get_db),
) -> List[Event]:
    """List all events."""
    result = await db.execute(select(Event).order_by(Event.created_at.desc()))
    return list(result.scalars().all())


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(
    event_id: str,
    db: AsyncSession = Depends(get_db),
) -> Event:
    """Get an event by ID."""
    result = await db.execute(select(Event).where(Event.id == event_id))
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
    result = await db.execute(select(Event).where(Event.id == event_id))
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
