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
from app.models.event import Event
from app.models.sub_event import SubEvent
from app.services.llm_service import LLMService, get_llm_service
from app.schemas.capture import (
    ActionType,
    IntentType,
    PaymentData,
    TaskData,
    CalendarEventData,
    VendorData,
    SubEventUpdateData,
    EventUpdateData,
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
        context: Optional[str] = None,
    ) -> tuple[dict, str]:
        """
        Extract intent and data from user input with optional context.
        
        Args:
            user_input: Natural language input from user
            event_id: The event this extraction is for
            db: Database session
            context: Optional context string with existing records
        
        Returns:
            Tuple of (extraction_result, log_id)
        """
        result = await self.llm_service.extract_intent_and_data(user_input, context)
        
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
        action: ActionType = ActionType.CREATE,
        reference_id: Optional[str] = None,
    ) -> tuple[bool, str, Optional[str]]:
        """
        Confirm extracted data and persist to database.
        
        Args:
            log_id: The AI log ID for this extraction
            event_id: The event ID
            intent: The intent type
            data: The extracted data
            db: Database session
            action: "create" for new records, "update" for modifications
            reference_id: ID of existing record to update (if action=update)
        
        Returns:
            Tuple of (success, message, record_id)
        """
        result = await db.execute(select(AILog).where(AILog.id == log_id))
        ai_log = result.scalar_one_or_none()
        
        if not ai_log:
            return False, "AI log not found", None
        
        try:
            record_id = None
            
            if intent == IntentType.PAYMENT:
                if action == ActionType.UPDATE and reference_id:
                    created_id = await self._update_payment(reference_id, data, db)
                    message = "Successfully updated payment"
                else:
                    created_id = await self._create_payment(event_id, data, db)
                    message = "Successfully created payment"
            elif intent == IntentType.TASK:
                created_id = await self._create_task(event_id, data, db)
                message = "Successfully created task"
            elif intent == IntentType.CALENDAR_EVENT:
                created_id = await self._create_calendar_event(event_id, data, db)
                message = "Successfully created calendar event"
            elif intent == IntentType.VENDOR:
                created_id = await self._create_vendor(event_id, data, db)
                message = "Successfully created vendor"
            elif intent == IntentType.SUB_EVENT_UPDATE:
                created_id, message = await self._handle_sub_event_update(event_id, data, db)
            elif intent == IntentType.EVENT_UPDATE:
                created_id, message = await self._update_event(event_id, data, db)
            else:
                ai_log.status = AILogStatus.ERROR
                await db.commit()
                return False, f"Unknown intent: {intent}", None
            
            ai_log.status = AILogStatus.SUCCESS
            await db.commit()
            
            return True, message, created_id

            
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
    
    async def _update_payment(
        self,
        payment_id: str,
        data: dict,
        db: AsyncSession,
    ) -> str:
        """Update an existing payment record (e.g., paying remaining balance or refund)."""
        import re
        
        result = await db.execute(select(Payment).where(Payment.id == payment_id))
        payment = result.scalar_one_or_none()
        
        if not payment:
            raise ValueError(f"Payment {payment_id} not found")
        
        amount_paid = data.get("amount_paid")
        remaining = data.get("remaining_balance")
        
        is_refund = (
            (amount_paid == 0 or amount_paid == "0") and 
            (remaining == 0 or remaining == "0")
        )
        
        if is_refund:
            payment.amount = 0
            payment.due_date = None
            payment.paid_date = None
            if payment.notes:
                payment.notes = re.sub(r"REMAINING_BALANCE:\s*\d+(?:\.\d+)?;?\s*", "", payment.notes).strip("; ")
        else:
            if amount_paid:
                amount = amount_paid
                if isinstance(amount, str):
                    amount = float(amount)
                payment.amount = (payment.amount or 0) + amount
            
            if data.get("payment_date"):
                if isinstance(data["payment_date"], str):
                    payment.paid_date = date.fromisoformat(data["payment_date"])
                else:
                    payment.paid_date = data["payment_date"]
            elif amount_paid:
                payment.paid_date = date.today()
            
            if remaining is not None:
                remaining_val = float(remaining) if isinstance(remaining, str) else remaining
                if remaining_val == 0:
                    payment.due_date = None
                    if payment.notes:
                        payment.notes = re.sub(r"REMAINING_BALANCE:\s*\d+(?:\.\d+)?;?\s*", "", payment.notes).strip("; ")
                else:
                    if payment.notes:
                        if "REMAINING_BALANCE:" in payment.notes:
                            payment.notes = re.sub(
                                r"REMAINING_BALANCE:\s*\d+(?:\.\d+)?",
                                f"REMAINING_BALANCE: {remaining_val}",
                                payment.notes
                            )
                        else:
                            payment.notes = f"{payment.notes}; REMAINING_BALANCE: {remaining_val}"
                    else:
                        payment.notes = f"REMAINING_BALANCE: {remaining_val}"
        
        if data.get("method"):
            payment.method = data["method"]
        
        if data.get("notes"):
            existing_notes = payment.notes or ""
            payment.notes = f"{existing_notes}; {data['notes']}".strip("; ")
        
        await db.commit()
        await db.refresh(payment)
        return payment.id
    
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
        
        amount = data.get("amount_paid") or 0
        remaining_balance = data.get("remaining_balance") or 0
        
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
        
        notes_parts = []
        if data.get("notes"):
            notes_parts.append(data["notes"])
        if vendor_name:
            notes_parts.append(f"Vendor: {vendor_name}")
        if remaining_balance:
            notes_parts.append(f"REMAINING_BALANCE: {remaining_balance}")
        
        payment = Payment(
            event_id=event_id,
            vendor_id=vendor_id,
            amount=amount,
            paid_date=paid_date,
            due_date=due_date,
            method=data.get("method"),
            notes="; ".join(notes_parts) if notes_parts else None,
        )
        db.add(payment)
        await db.commit()
        await db.refresh(payment)
        
        # Auto-create a task for upcoming payment if there's a due date with remaining balance
        remaining_balance = data.get("remaining_balance")
        if due_date and remaining_balance:
            try:
                remaining_amount = float(remaining_balance) if remaining_balance else 0
                if remaining_amount > 0:
                    await self._create_payment_reminder_task(
                        event_id=event_id,
                        vendor_name=vendor_name or "Vendor",
                        amount=remaining_amount,
                        due_date=due_date,
                        db=db,
                    )
            except (ValueError, TypeError):
                pass
        
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
    
    async def _create_payment_reminder_task(
        self,
        event_id: str,
        vendor_name: str,
        amount: float,
        due_date: date,
        db: AsyncSession,
    ) -> str:
        """Auto-create a task to remind about an upcoming payment."""
        from app.models.task import TaskStatus, TaskPriority
        
        task = Task(
            event_id=event_id,
            title=f"Payment due: ${amount:,.0f} to {vendor_name}",
            description=f"Reminder: ${amount:,.2f} payment due to {vendor_name}",
            due_date=due_date,
            status=TaskStatus.PENDING,
            priority=TaskPriority.HIGH,
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
    
    async def _handle_sub_event_update(
        self,
        event_id: str,
        data: dict,
        db: AsyncSession,
    ) -> tuple[Optional[str], str]:
        """Handle sub-event add/update/cancel/reschedule actions."""
        from datetime import time as dt_time
        
        action = data.get("action", "").lower()
        sub_event_name = data.get("sub_event_name", "")
        
        if action == "add":
            new_date = data.get("new_date")
            if isinstance(new_date, str):
                new_date = date.fromisoformat(new_date)
            
            start_time = None
            if data.get("new_start_time"):
                time_str = data["new_start_time"]
                if isinstance(time_str, str):
                    parts = time_str.split(":")
                    start_time = dt_time(int(parts[0]), int(parts[1]))
                else:
                    start_time = time_str
            
            end_time = None
            if data.get("new_end_time"):
                time_str = data["new_end_time"]
                if isinstance(time_str, str):
                    parts = time_str.split(":")
                    end_time = dt_time(int(parts[0]), int(parts[1]))
                else:
                    end_time = time_str
            
            sub_event = SubEvent(
                event_id=event_id,
                name=data.get("new_name") or sub_event_name or "New Sub-Event",
                date=new_date or date.today(),
                start_time=start_time,
                end_time=end_time,
                location=data.get("new_location"),
                description=data.get("description"),
            )
            db.add(sub_event)
            await db.commit()
            await db.refresh(sub_event)
            return sub_event.id, f"Successfully added sub-event: {sub_event.name}"
        
        result = await db.execute(
            select(SubEvent).where(
                SubEvent.event_id == event_id,
                SubEvent.name.ilike(f"%{sub_event_name}%"),
            )
        )
        sub_event = result.scalar_one_or_none()
        
        if not sub_event:
            return None, f"Sub-event '{sub_event_name}' not found"
        
        if action == "cancel":
            name = sub_event.name
            await db.delete(sub_event)
            await db.commit()
            return None, f"Successfully cancelled sub-event: {name}"
        
        elif action == "update":
            if data.get("new_name"):
                sub_event.name = data["new_name"]
            if data.get("new_location"):
                sub_event.location = data["new_location"]
            if data.get("description"):
                sub_event.description = data["description"]
            
            await db.commit()
            await db.refresh(sub_event)
            return sub_event.id, f"Successfully updated sub-event: {sub_event.name}"
        
        elif action == "reschedule":
            if data.get("new_date"):
                new_date = data["new_date"]
                if isinstance(new_date, str):
                    new_date = date.fromisoformat(new_date)
                sub_event.date = new_date
            
            if data.get("new_start_time"):
                time_str = data["new_start_time"]
                if isinstance(time_str, str):
                    parts = time_str.split(":")
                    sub_event.start_time = dt_time(int(parts[0]), int(parts[1]))
                else:
                    sub_event.start_time = time_str
            
            if data.get("new_end_time"):
                time_str = data["new_end_time"]
                if isinstance(time_str, str):
                    parts = time_str.split(":")
                    sub_event.end_time = dt_time(int(parts[0]), int(parts[1]))
                else:
                    sub_event.end_time = time_str
            
            if data.get("new_location"):
                sub_event.location = data["new_location"]
            
            await db.commit()
            await db.refresh(sub_event)
            return sub_event.id, f"Successfully rescheduled sub-event: {sub_event.name}"
        
        return None, f"Unknown action: {action}"
    
    async def _update_event(
        self,
        event_id: str,
        data: dict,
        db: AsyncSession,
    ) -> tuple[Optional[str], str]:
        """Update main event details."""
        result = await db.execute(select(Event).where(Event.id == event_id))
        event = result.scalar_one_or_none()
        
        if not event:
            return None, "Event not found"
        
        if data.get("name"):
            event.name = data["name"]
        if data.get("start_date"):
            start_date = data["start_date"]
            if isinstance(start_date, str):
                start_date = date.fromisoformat(start_date)
            event.start_date = start_date
        if data.get("end_date"):
            end_date = data["end_date"]
            if isinstance(end_date, str):
                end_date = date.fromisoformat(end_date)
            event.end_date = end_date
        if data.get("location"):
            event.location = data["location"]
        if data.get("location_city"):
            event.location_city = data["location_city"]
        if data.get("description"):
            event.description = data["description"]
        
        await db.commit()
        await db.refresh(event)
        return event.id, f"Successfully updated event: {event.name}"


def get_extraction_service() -> ExtractionService:
    """Get extraction service instance."""
    return ExtractionService()
