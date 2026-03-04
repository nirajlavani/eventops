import json
from typing import Optional
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_log import AILog, AILogStatus
from app.models.vendor import Vendor
from app.models.payment import Payment
from app.models.task import Task
from app.models.calendar_event import CalendarEvent
from app.services.llm_service import LLMService, get_llm_service
from app.schemas.capture import (
    IntentType,
    PaymentData,
    TaskData,
    CalendarEventData,
    VendorData,
)


class ExtractionService:
    """Service for extracting structured data from natural language."""
    
    def __init__(self, llm_service: Optional[LLMService] = None):
        self.llm_service = llm_service or get_llm_service()
    
    async def extract(
        self,
        user_input: str,
        event_id: str,
        db: AsyncSession,
    ) -> tuple[dict, str]:
        """
        Extract intent and data from user input.
        
        Returns:
            Tuple of (extraction_result, log_id)
        """
        result = await self.llm_service.extract_intent_and_data(user_input)
        
        ai_log = AILog(
            event_id=event_id,
            user_input=user_input,
            llm_output=json.dumps(result),
            intent=result.get("intent"),
            status=AILogStatus.PENDING,
        )
        db.add(ai_log)
        await db.commit()
        await db.refresh(ai_log)
        
        return result, ai_log.id
    
    async def confirm_and_persist(
        self,
        log_id: str,
        event_id: str,
        intent: IntentType,
        data: dict,
        db: AsyncSession,
    ) -> tuple[bool, str, Optional[str]]:
        """
        Confirm extracted data and persist to database.
        
        Returns:
            Tuple of (success, message, created_id)
        """
        result = await db.execute(select(AILog).where(AILog.id == log_id))
        ai_log = result.scalar_one_or_none()
        
        if not ai_log:
            return False, "AI log not found", None
        
        try:
            created_id = None
            
            if intent == IntentType.PAYMENT:
                created_id = await self._create_payment(event_id, data, db)
            elif intent == IntentType.TASK:
                created_id = await self._create_task(event_id, data, db)
            elif intent == IntentType.CALENDAR_EVENT:
                created_id = await self._create_calendar_event(event_id, data, db)
            elif intent == IntentType.VENDOR:
                created_id = await self._create_vendor(event_id, data, db)
            else:
                ai_log.status = AILogStatus.ERROR
                await db.commit()
                return False, f"Unknown intent: {intent}", None
            
            ai_log.status = AILogStatus.SUCCESS
            await db.commit()
            
            return True, f"Successfully created {intent.value}", created_id
            
        except Exception as e:
            ai_log.status = AILogStatus.ERROR
            await db.commit()
            return False, str(e), None
    
    async def reject(self, log_id: str, db: AsyncSession) -> bool:
        """Mark an extraction as rejected."""
        result = await db.execute(select(AILog).where(AILog.id == log_id))
        ai_log = result.scalar_one_or_none()
        
        if not ai_log:
            return False
        
        ai_log.status = AILogStatus.REJECTED
        await db.commit()
        return True
    
    async def _create_payment(
        self,
        event_id: str,
        data: dict,
        db: AsyncSession,
    ) -> str:
        """Create a payment from extracted data."""
        vendor_id = None
        vendor_name = data.get("vendor_name")
        
        if vendor_name:
            result = await db.execute(
                select(Vendor).where(
                    Vendor.event_id == event_id,
                    Vendor.name.ilike(f"%{vendor_name}%"),
                )
            )
            vendor = result.scalar_one_or_none()
            if vendor:
                vendor_id = vendor.id
        
        amount = data.get("amount_paid") or data.get("remaining_balance") or 0
        
        due_date = None
        if data.get("due_date"):
            if isinstance(data["due_date"], str):
                due_date = date.fromisoformat(data["due_date"])
            else:
                due_date = data["due_date"]
        
        paid_date = None
        if data.get("payment_date"):
            if isinstance(data["payment_date"], str):
                paid_date = date.fromisoformat(data["payment_date"])
            else:
                paid_date = data["payment_date"]
        elif data.get("amount_paid"):
            paid_date = date.today()
        
        payment = Payment(
            event_id=event_id,
            vendor_id=vendor_id,
            amount=amount,
            paid_date=paid_date,
            due_date=due_date,
            method=data.get("method"),
            notes=data.get("notes"),
        )
        db.add(payment)
        await db.commit()
        await db.refresh(payment)
        return payment.id
    
    async def _create_task(
        self,
        event_id: str,
        data: dict,
        db: AsyncSession,
    ) -> str:
        """Create a task from extracted data."""
        from app.models.task import TaskStatus, TaskPriority
        
        due_date = None
        if data.get("due_date"):
            if isinstance(data["due_date"], str):
                due_date = date.fromisoformat(data["due_date"])
            else:
                due_date = data["due_date"]
        
        priority_map = {
            "low": TaskPriority.LOW,
            "medium": TaskPriority.MEDIUM,
            "high": TaskPriority.HIGH,
        }
        priority = priority_map.get(data.get("priority", "medium"), TaskPriority.MEDIUM)
        
        task = Task(
            event_id=event_id,
            title=data.get("title", "Untitled Task"),
            description=data.get("description"),
            due_date=due_date,
            status=TaskStatus.PENDING,
            priority=priority,
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)
        return task.id
    
    async def _create_calendar_event(
        self,
        event_id: str,
        data: dict,
        db: AsyncSession,
    ) -> str:
        """Create a calendar event from extracted data."""
        from datetime import time as dt_time
        
        event_date = data.get("event_date")
        if isinstance(event_date, str):
            event_date = date.fromisoformat(event_date)
        
        event_time = None
        if data.get("event_time"):
            time_str = data["event_time"]
            if isinstance(time_str, str):
                parts = time_str.split(":")
                event_time = dt_time(int(parts[0]), int(parts[1]))
            else:
                event_time = time_str
        
        calendar_event = CalendarEvent(
            event_id=event_id,
            title=data.get("title", "Untitled Event"),
            event_date=event_date or date.today(),
            event_time=event_time,
            location=data.get("location"),
            notes=data.get("notes"),
        )
        db.add(calendar_event)
        await db.commit()
        await db.refresh(calendar_event)
        return calendar_event.id
    
    async def _create_vendor(
        self,
        event_id: str,
        data: dict,
        db: AsyncSession,
    ) -> str:
        """Create a vendor from extracted data."""
        vendor = Vendor(
            event_id=event_id,
            name=data.get("name", "Unknown Vendor"),
            category=data.get("category"),
            contact_info=data.get("contact_info"),
            notes=data.get("notes"),
        )
        db.add(vendor)
        await db.commit()
        await db.refresh(vendor)
        return vendor.id


def get_extraction_service() -> ExtractionService:
    """Get extraction service instance."""
    return ExtractionService()
