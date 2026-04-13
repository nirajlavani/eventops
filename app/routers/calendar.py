from datetime import date
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.event import Event
from app.models.calendar_event import CalendarEvent
from app.models.task import Task
from app.models.payment import Payment
from app.models.vendor import Vendor
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


@router.get("/grid", response_model=None)
async def get_calendar_grid_data(
    event_id: str,
    start: date = Query(..., description="Range start date (inclusive)"),
    end: date = Query(..., description="Range end date (inclusive)"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return calendar events and tasks that fall within a date range for grid display."""
    await get_event_or_404(event_id, db)

    cal_result = await db.execute(
        select(CalendarEvent)
        .where(
            CalendarEvent.event_id == event_id,
            or_(
                and_(
                    CalendarEvent.event_date >= start,
                    CalendarEvent.event_date <= end,
                ),
                and_(
                    CalendarEvent.end_date.isnot(None),
                    CalendarEvent.end_date >= start,
                    CalendarEvent.event_date <= end,
                ),
            ),
        )
        .order_by(CalendarEvent.event_date.asc())
    )
    calendar_events = list(cal_result.scalars().all())

    task_result = await db.execute(
        select(Task)
        .where(
            Task.event_id == event_id,
            Task.due_date.isnot(None),
            Task.due_date >= start,
            Task.due_date <= end,
        )
        .order_by(Task.due_date.asc())
    )
    tasks = list(task_result.scalars().all())

    payment_result = await db.execute(
        select(Payment)
        .where(
            Payment.event_id == event_id,
            Payment.paid_date.isnot(None),
            Payment.paid_date >= start,
            Payment.paid_date <= end,
        )
        .order_by(Payment.paid_date.asc())
    )
    payments = list(payment_result.scalars().all())

    vendor_ids = {p.vendor_id for p in payments if p.vendor_id}
    vendor_map: dict[str, str] = {}
    if vendor_ids:
        vendor_result = await db.execute(
            select(Vendor).where(Vendor.id.in_(vendor_ids))
        )
        vendor_map = {v.id: v.name for v in vendor_result.scalars().all()}

    return {
        "calendar_events": [
            {
                "id": ce.id,
                "event_id": ce.event_id,
                "title": ce.title,
                "event_date": ce.event_date.isoformat(),
                "end_date": ce.end_date.isoformat() if ce.end_date else None,
                "event_time": ce.event_time.isoformat() if ce.event_time else None,
                "all_day": ce.all_day,
                "location": ce.location,
                "notes": ce.notes,
                "created_at": ce.created_at.isoformat(),
                "updated_at": ce.updated_at.isoformat(),
            }
            for ce in calendar_events
        ],
        "tasks": [
            {
                "id": t.id,
                "title": t.title,
                "due_date": t.due_date.isoformat() if t.due_date else None,
                "due_time": t.due_time.isoformat() if t.due_time else None,
                "status": t.status.value if t.status else None,
                "priority": t.priority.value if t.priority else None,
                "vendor_category": t.vendor_category,
            }
            for t in tasks
        ],
        "payments": [
            {
                "id": p.id,
                "event_id": p.event_id,
                "vendor_id": p.vendor_id,
                "vendor_name": vendor_map.get(p.vendor_id) if p.vendor_id else None,
                "amount": str(p.amount),
                "paid_date": p.paid_date.isoformat() if p.paid_date else None,
                "due_date": p.due_date.isoformat() if p.due_date else None,
                "method": p.method,
                "notes": p.notes,
                "created_at": p.created_at.isoformat(),
            }
            for p in payments
        ],
    }


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
