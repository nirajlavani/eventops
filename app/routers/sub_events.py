from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.event import Event
from app.models.sub_event import SubEvent
from app.schemas.sub_event import (
    SubEventCreate,
    SubEventUpdate,
    SubEventResponse,
    SubEventBulkCreate,
    SubEventReorder,
)

router = APIRouter()


async def get_event_or_404(event_id: str, db: AsyncSession) -> Event:
    """Get event by ID or raise 404."""
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )
    return event


@router.post("", response_model=SubEventResponse, status_code=status.HTTP_201_CREATED)
async def create_sub_event(
    event_id: str,
    sub_event_data: SubEventCreate,
    db: AsyncSession = Depends(get_db),
) -> SubEvent:
    """Create a new sub-event."""
    await get_event_or_404(event_id, db)
    
    sub_event = SubEvent(
        event_id=event_id,
        **sub_event_data.model_dump(),
    )
    db.add(sub_event)
    await db.commit()
    await db.refresh(sub_event)
    return sub_event


@router.post("/bulk", response_model=List[SubEventResponse], status_code=status.HTTP_201_CREATED)
async def create_sub_events_bulk(
    event_id: str,
    bulk_data: SubEventBulkCreate,
    db: AsyncSession = Depends(get_db),
) -> List[SubEvent]:
    """Create multiple sub-events at once."""
    await get_event_or_404(event_id, db)
    
    sub_events = []
    for idx, sub_event_data in enumerate(bulk_data.sub_events):
        sub_event = SubEvent(
            event_id=event_id,
            order=sub_event_data.order if sub_event_data.order else idx,
            **sub_event_data.model_dump(exclude={"order"}),
        )
        db.add(sub_event)
        sub_events.append(sub_event)
    
    await db.commit()
    for sub_event in sub_events:
        await db.refresh(sub_event)
    
    return sub_events


@router.get("", response_model=List[SubEventResponse])
async def list_sub_events(
    event_id: str,
    db: AsyncSession = Depends(get_db),
) -> List[SubEvent]:
    """List all sub-events for an event."""
    await get_event_or_404(event_id, db)
    
    result = await db.execute(
        select(SubEvent)
        .where(SubEvent.event_id == event_id)
        .order_by(SubEvent.order, SubEvent.date)
    )
    return list(result.scalars().all())


@router.get("/{sub_event_id}", response_model=SubEventResponse)
async def get_sub_event(
    event_id: str,
    sub_event_id: str,
    db: AsyncSession = Depends(get_db),
) -> SubEvent:
    """Get a sub-event by ID."""
    await get_event_or_404(event_id, db)
    
    result = await db.execute(
        select(SubEvent).where(
            SubEvent.id == sub_event_id,
            SubEvent.event_id == event_id,
        )
    )
    sub_event = result.scalar_one_or_none()
    if not sub_event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sub-event not found",
        )
    return sub_event


@router.put("/{sub_event_id}", response_model=SubEventResponse)
async def update_sub_event(
    event_id: str,
    sub_event_id: str,
    sub_event_data: SubEventUpdate,
    db: AsyncSession = Depends(get_db),
) -> SubEvent:
    """Update a sub-event."""
    await get_event_or_404(event_id, db)
    
    result = await db.execute(
        select(SubEvent).where(
            SubEvent.id == sub_event_id,
            SubEvent.event_id == event_id,
        )
    )
    sub_event = result.scalar_one_or_none()
    if not sub_event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sub-event not found",
        )
    
    update_data = sub_event_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(sub_event, field, value)
    
    await db.commit()
    await db.refresh(sub_event)
    return sub_event


@router.delete("/{sub_event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sub_event(
    event_id: str,
    sub_event_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a sub-event."""
    await get_event_or_404(event_id, db)
    
    result = await db.execute(
        select(SubEvent).where(
            SubEvent.id == sub_event_id,
            SubEvent.event_id == event_id,
        )
    )
    sub_event = result.scalar_one_or_none()
    if not sub_event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sub-event not found",
        )
    
    await db.delete(sub_event)
    await db.commit()


@router.put("/reorder", response_model=List[SubEventResponse])
async def reorder_sub_events(
    event_id: str,
    reorder_data: SubEventReorder,
    db: AsyncSession = Depends(get_db),
) -> List[SubEvent]:
    """Reorder sub-events by providing ordered list of IDs."""
    await get_event_or_404(event_id, db)
    
    result = await db.execute(
        select(SubEvent).where(SubEvent.event_id == event_id)
    )
    sub_events = {se.id: se for se in result.scalars().all()}
    
    reordered = []
    for idx, sub_event_id in enumerate(reorder_data.sub_event_ids):
        if sub_event_id not in sub_events:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Sub-event {sub_event_id} not found in this event",
            )
        sub_events[sub_event_id].order = idx
        reordered.append(sub_events[sub_event_id])
    
    await db.commit()
    for sub_event in reordered:
        await db.refresh(sub_event)
    
    return reordered
