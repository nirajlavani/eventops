from datetime import date, timedelta
from typing import List
from decimal import Decimal

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event
from app.models.task import Task, TaskStatus
from app.models.payment import Payment
from app.models.calendar_event import CalendarEvent
from app.models.vendor import Vendor
from app.services.llm_service import LLMService, get_llm_service


class PlanningService:
    """Service for AI-powered planning recommendations."""
    
    def __init__(self, llm_service: LLMService = None):
        self.llm_service = llm_service or get_llm_service()
    
    async def get_focus_recommendations(
        self,
        event_id: str,
        query: str,
        db: AsyncSession,
    ) -> dict:
        """
        Get AI-powered focus recommendations for an event.
        
        Args:
            event_id: The event ID
            query: User's planning query
            db: Database session
        
        Returns:
            Dict with summary, priority_items, and recommendations
        """
        context = await self._build_context(event_id, db)
        
        result = await self.llm_service.generate_planning_response(query, context)
        
        return result
    
    async def _build_context(self, event_id: str, db: AsyncSession) -> dict:
        """Build context dict with event data for the LLM."""
        today = date.today()
        week_from_now = today + timedelta(days=7)
        month_from_now = today + timedelta(days=30)
        
        event_result = await db.execute(
            select(Event).where(Event.id == event_id)
        )
        event = event_result.scalar_one_or_none()
        
        tasks_result = await db.execute(
            select(Task).where(
                Task.event_id == event_id,
                Task.status != TaskStatus.COMPLETED,
            )
        )
        tasks = tasks_result.scalars().all()
        
        payments_result = await db.execute(
            select(Payment).where(
                Payment.event_id == event_id,
                or_(
                    Payment.due_date != None,
                    Payment.paid_date == None,
                ),
            )
        )
        payments = payments_result.scalars().all()
        
        calendar_result = await db.execute(
            select(CalendarEvent).where(
                CalendarEvent.event_id == event_id,
                CalendarEvent.event_date >= today,
                CalendarEvent.event_date <= month_from_now,
            ).order_by(CalendarEvent.event_date.asc())
        )
        calendar_events = calendar_result.scalars().all()
        
        vendors_result = await db.execute(
            select(Vendor).where(Vendor.event_id == event_id)
        )
        vendors = vendors_result.scalars().all()
        vendor_map = {v.id: v.name for v in vendors}
        
        context = {
            "event": {
                "name": event.name if event else "Unknown Event",
                "type": event.event_type if event else None,
                "date": str(event.event_date) if event and event.event_date else None,
            },
            "today": str(today),
            "tasks": [
                {
                    "title": t.title,
                    "due_date": str(t.due_date) if t.due_date else None,
                    "priority": t.priority.value if t.priority else "medium",
                    "status": t.status.value if t.status else "pending",
                    "overdue": t.due_date < today if t.due_date else False,
                    "due_this_week": t.due_date <= week_from_now if t.due_date else False,
                }
                for t in tasks
            ],
            "upcoming_payments": [
                {
                    "vendor": vendor_map.get(p.vendor_id, "Unknown"),
                    "amount": float(p.amount),
                    "due_date": str(p.due_date) if p.due_date else None,
                    "is_paid": p.paid_date is not None,
                    "overdue": p.due_date < today if p.due_date and not p.paid_date else False,
                }
                for p in payments
                if p.due_date and not p.paid_date
            ],
            "calendar_events": [
                {
                    "title": ce.title,
                    "date": str(ce.event_date),
                    "time": str(ce.event_time) if ce.event_time else None,
                    "location": ce.location,
                    "days_until": (ce.event_date - today).days,
                }
                for ce in calendar_events
            ],
            "vendor_count": len(vendors),
        }
        
        return context


def get_planning_service() -> PlanningService:
    """Get planning service instance."""
    return PlanningService()
