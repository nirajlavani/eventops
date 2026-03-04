from datetime import date, timedelta
from decimal import Decimal
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.event import Event
from app.models.vendor import Vendor
from app.models.payment import Payment
from app.models.task import Task, TaskStatus
from app.models.calendar_event import CalendarEvent
from app.schemas.dashboard import (
    DashboardResponse,
    UpcomingPayment,
    OpenTask,
    UpcomingCalendarEvent,
    VendorSummary,
    FinancialSummary,
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


@router.get("", response_model=DashboardResponse)
async def get_dashboard(
    event_id: str,
    db: AsyncSession = Depends(get_db),
) -> DashboardResponse:
    """
    Get dashboard summary for an event.
    
    Returns:
    - Upcoming payments (next 30 days)
    - Open tasks (pending/in_progress)
    - Upcoming calendar events (next 14 days)
    - Vendor summary
    - Financial summary
    """
    event = await get_event_or_404(event_id, db)
    
    today = date.today()
    thirty_days = today + timedelta(days=30)
    fourteen_days = today + timedelta(days=14)
    
    vendors_result = await db.execute(
        select(Vendor).where(Vendor.event_id == event_id)
    )
    vendors = vendors_result.scalars().all()
    vendor_map = {v.id: v.name for v in vendors}
    
    payments_result = await db.execute(
        select(Payment).where(
            Payment.event_id == event_id,
            Payment.due_date != None,
            Payment.due_date <= thirty_days,
            Payment.paid_date == None,
        ).order_by(Payment.due_date.asc())
    )
    payments = payments_result.scalars().all()
    
    upcoming_payments = [
        UpcomingPayment(
            id=p.id,
            vendor_name=vendor_map.get(p.vendor_id),
            amount=p.amount,
            due_date=p.due_date,
            notes=p.notes,
        )
        for p in payments
    ]
    
    tasks_result = await db.execute(
        select(Task).where(
            Task.event_id == event_id,
            Task.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS]),
        ).order_by(Task.due_date.asc().nullslast(), Task.priority.desc())
    )
    tasks = tasks_result.scalars().all()
    
    open_tasks = [
        OpenTask(
            id=t.id,
            title=t.title,
            due_date=t.due_date,
            priority=t.priority.value if t.priority else "medium",
            status=t.status.value if t.status else "pending",
        )
        for t in tasks
    ]
    
    calendar_result = await db.execute(
        select(CalendarEvent).where(
            CalendarEvent.event_id == event_id,
            CalendarEvent.event_date >= today,
            CalendarEvent.event_date <= fourteen_days,
        ).order_by(CalendarEvent.event_date.asc(), CalendarEvent.event_time.asc())
    )
    calendar_events = calendar_result.scalars().all()
    
    upcoming_events = [
        UpcomingCalendarEvent(
            id=ce.id,
            title=ce.title,
            event_date=ce.event_date,
            event_time=str(ce.event_time) if ce.event_time else None,
            location=ce.location,
        )
        for ce in calendar_events
    ]
    
    category_counts = defaultdict(int)
    for v in vendors:
        category = v.category or "uncategorized"
        category_counts[category] += 1
    
    vendor_summary = VendorSummary(
        total_vendors=len(vendors),
        by_category=dict(category_counts),
    )
    
    all_payments_result = await db.execute(
        select(Payment).where(Payment.event_id == event_id)
    )
    all_payments = all_payments_result.scalars().all()
    
    total_paid = Decimal("0")
    total_upcoming = Decimal("0")
    vendor_totals = defaultdict(lambda: {"paid": Decimal("0"), "upcoming": Decimal("0")})
    
    for p in all_payments:
        vendor_name = vendor_map.get(p.vendor_id, "Other")
        if p.paid_date:
            total_paid += p.amount
            vendor_totals[vendor_name]["paid"] += p.amount
        elif p.due_date:
            total_upcoming += p.amount
            vendor_totals[vendor_name]["upcoming"] += p.amount
    
    by_vendor = {
        name: {
            "paid": float(data["paid"]),
            "upcoming": float(data["upcoming"]),
        }
        for name, data in vendor_totals.items()
    }
    
    financial_summary = FinancialSummary(
        total_paid=total_paid,
        total_upcoming=total_upcoming,
        by_vendor=by_vendor,
    )
    
    return DashboardResponse(
        event_id=event_id,
        event_name=event.name,
        upcoming_payments=upcoming_payments,
        open_tasks=open_tasks,
        upcoming_events=upcoming_events,
        vendor_summary=vendor_summary,
        financial_summary=financial_summary,
    )
