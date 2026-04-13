import json
import logging
from typing import Optional
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select, func, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from app.models.ai_log import AILog, AILogStatus
from app.models.vendor import Vendor
from app.models.payment import Payment
from app.models.task import Task, TaskStatus
from app.models.calendar_event import CalendarEvent
from app.models.event import Event
from app.models.sub_event import SubEvent
from app.services.llm_service import LLMService, get_llm_service
from app.services.metrics import record_metric
from app.models.ai_metric import MetricType
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
        conversation_history: Optional[list[dict]] = None,
    ) -> tuple[dict, str]:
        """
        Extract intent and data from user input with optional context.
        
        Args:
            user_input: Natural language input from user
            event_id: The event this extraction is for
            db: Database session
            context: Optional context string with existing records
            conversation_history: Optional list of recent conversation messages
        
        Returns:
            Tuple of (extraction_result, log_id)
        """
        result = await self.llm_service.extract_intent_and_data(
            user_input,
            context,
            conversation_history
        )

        usage = result.pop("_usage", {})

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

        await record_metric(
            db,
            metric_type=MetricType.EXTRACTION,
            event_id=event_id,
            ai_log_id=ai_log.id,
            model_name=usage.get("model"),
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"),
            latency_ms=usage.get("latency_ms"),
            intent=result.get("intent"),
            confidence=result.get("confidence"),
            status="success",
        )

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
            
            # Handle DELETE action
            if action == ActionType.DELETE and reference_id:
                deleted_id = await self._delete_record(intent, reference_id, db)
                if deleted_id:
                    ai_log.status = AILogStatus.SUCCESS
                    await db.commit()
                    return True, f"Successfully deleted {intent.value}", deleted_id
                else:
                    ai_log.status = AILogStatus.ERROR
                    await db.commit()
                    return False, f"Record not found or could not be deleted", None
            
            if intent == IntentType.PAYMENT:
                replace_vendor = data.get("replace_pending_vendor")
                if replace_vendor:
                    await self._delete_pending_payments_for_vendor(
                        event_id, replace_vendor, db
                    )
                
                if action == ActionType.UPDATE and reference_id:
                    created_id = await self._update_payment(reference_id, data, db)
                    message = "Successfully updated payment"
                elif action == ActionType.UPDATE and "items" in data and isinstance(data["items"], list):
                    updated_count = 0
                    for item in data["items"]:
                        matched = await self._find_and_update_payment(event_id, item, db)
                        if matched:
                            updated_count += 1
                    created_id = None
                    message = f"Successfully updated {updated_count} payments"
                elif "items" in data and isinstance(data["items"], list):
                    created_ids = []
                    for item in data["items"]:
                        pid = await self._create_payment(event_id, item, db)
                        created_ids.append(pid)
                    created_id = created_ids[0] if created_ids else None
                    message = f"Successfully created {len(created_ids)} payments"
                else:
                    created_id = await self._create_payment(event_id, data, db)
                    message = "Successfully created payment"
            elif intent == IntentType.TASK:
                if action == ActionType.UPDATE and reference_id:
                    created_id = await self._update_task_by_id(reference_id, data, db)
                    message = "Successfully updated task"
                elif data.get("items") and isinstance(data["items"], list):
                    created_ids = []
                    for item in data["items"]:
                        task_id = await self._create_task(event_id, item, db)
                        created_ids.append(task_id)
                    created_id = ",".join(created_ids)
                    message = f"Successfully created {len(created_ids)} tasks"
                else:
                    created_id = await self._create_task(event_id, data, db)
                    message = "Successfully created task"
            elif intent == IntentType.CALENDAR_EVENT:
                created_id = await self._create_calendar_event(event_id, data, db)
                message = "Successfully created calendar event"
            elif intent == IntentType.VENDOR:
                if action == ActionType.UPDATE:
                    created_id = await self._update_vendor_by_name(event_id, data, db)
                    message = "Successfully updated vendor" if created_id else "Vendor not found"
                elif action == ActionType.DELETE and reference_id:
                    deleted = await self._delete_vendor_cascade(event_id, reference_id, db)
                    message = "Successfully deleted vendor and associated records" if deleted else "Vendor not found"
                    created_id = reference_id if deleted else None
                else:
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
    
    async def _delete_record(
        self,
        intent: IntentType,
        record_id: str,
        db: AsyncSession,
    ) -> Optional[str]:
        """
        Delete a record based on intent type.
        
        Args:
            intent: The type of record to delete
            record_id: The ID of the record to delete
            db: Database session
            
        Returns:
            The deleted record ID if successful, None if not found
        """
        model_map = {
            IntentType.PAYMENT: Payment,
            IntentType.TASK: Task,
            IntentType.VENDOR: Vendor,
            IntentType.CALENDAR_EVENT: CalendarEvent,
        }
        
        model = model_map.get(intent)
        if not model:
            return None
        
        result = await db.execute(select(model).where(model.id == record_id))
        record = result.scalar_one_or_none()
        
        if not record:
            return None
        
        await db.delete(record)
        await db.commit()
        return record_id
    
    async def _delete_vendor_cascade(
        self,
        event_id: str,
        vendor_id: str,
        db: AsyncSession,
    ) -> bool:
        """Delete a vendor and all associated payments and tasks."""
        result = await db.execute(select(Vendor).where(Vendor.id == vendor_id))
        vendor = result.scalar_one_or_none()
        if not vendor:
            return False

        payments = await db.execute(
            select(Payment).where(Payment.vendor_id == vendor_id)
        )
        for p in payments.scalars().all():
            await db.delete(p)

        tasks = await db.execute(
            select(Task).where(Task.vendor_id == vendor_id)
        )
        for t in tasks.scalars().all():
            await db.delete(t)

        await db.delete(vendor)
        await db.commit()
        return True

    async def _delete_pending_payments_for_vendor(
        self,
        event_id: str,
        vendor_name: str,
        db: AsyncSession,
    ) -> int:
        """Delete all unpaid pending payments (and their reminder tasks) for a vendor.
        
        Used when a user splits a remaining balance into individual installments,
        replacing the single pending payment placeholder.
        """
        vendor = await self._find_vendor_by_name(event_id, vendor_name, db)
        if not vendor:
            return 0
        
        payments_result = await db.execute(
            select(Payment).where(
                Payment.event_id == event_id,
                Payment.vendor_id == vendor.id,
                Payment.paid_date.is_(None),
            )
        )
        pending_payments = payments_result.scalars().all()
        
        deleted_count = 0
        for payment in pending_payments:
            task_result = await db.execute(
                select(Task).where(
                    Task.event_id == event_id,
                    Task.title.contains(vendor_name),
                    Task.status == TaskStatus.PENDING,
                )
            )
            related_tasks = task_result.scalars().all()
            for task in related_tasks:
                await db.delete(task)
            
            await db.delete(payment)
            deleted_count += 1
        
        if deleted_count > 0:
            await db.flush()
        
        return deleted_count
    
    async def process_secondary_actions(
        self,
        event_id: str,
        secondary_actions: list[dict],
        db: AsyncSession,
    ) -> list[str]:
        """Process secondary actions emitted by the LLM alongside the primary intent."""
        messages = []
        for sa in secondary_actions:
            sa_intent_str = sa.get("intent", "unknown")
            sa_action_str = sa.get("action", "create")
            sa_data = sa.get("data", {})
            sa_ref_id = sa.get("reference_id")
            
            try:
                sa_intent = IntentType(sa_intent_str)
            except ValueError:
                continue
            
            try:
                if sa_intent == IntentType.EVENT_UPDATE:
                    _, msg = await self._update_event(event_id, sa_data, db)
                    messages.append(msg)
                elif sa_intent == IntentType.CALENDAR_EVENT:
                    await self._create_calendar_event(event_id, sa_data, db)
                    messages.append(f"Created calendar event: {sa_data.get('title', 'Event')}")
                elif sa_intent == IntentType.VENDOR:
                    if sa_action_str == "update":
                        await self._update_vendor_by_name(event_id, sa_data, db)
                        messages.append(f"Updated vendor: {sa_data.get('name', 'vendor')}")
                    else:
                        await self._create_vendor(event_id, sa_data, db)
                        messages.append(f"Created vendor: {sa_data.get('name', 'vendor')}")
                elif sa_intent == IntentType.PAYMENT:
                    await self._create_payment(event_id, sa_data, db)
                    messages.append("Created payment record")
                elif sa_intent == IntentType.TASK:
                    if sa_action_str == "update" and sa_ref_id:
                        await self._update_task_by_id(sa_ref_id, sa_data, db)
                        messages.append(f"Updated task: {sa_ref_id}")
                    elif sa_action_str == "delete" and sa_ref_id:
                        await self._delete_record(IntentType.TASK, sa_ref_id, db)
                        messages.append(f"Deleted task: {sa_ref_id}")
                    else:
                        await self._create_task(event_id, sa_data, db)
                        messages.append(f"Created task: {sa_data.get('title', 'Task')}")
            except Exception as e:
                logger.error(f"Secondary action failed ({sa_intent}): {e}")
        
        return messages
    
    async def _find_vendor_by_name(
        self,
        event_id: str,
        vendor_name: str,
        db: AsyncSession,
    ) -> Optional[Vendor]:
        """Find a vendor by name within an event. Returns the first match or None."""
        result = await db.execute(
            select(Vendor).where(
                Vendor.event_id == event_id,
                Vendor.name.ilike(f"%{vendor_name}%"),
            )
        )
        return result.scalars().first()

    async def _resolve_or_create_vendor(
        self,
        event_id: str,
        vendor_name: str,
        vendor_category: Optional[str] = None,
        vendor_notes: Optional[str] = None,
        db: AsyncSession = None,
        contact_info: Optional[str] = None,
    ) -> str:
        """Find existing vendor by name and update it, or create a new one. Returns vendor ID."""
        existing = await self._find_vendor_by_name(event_id, vendor_name, db)

        if existing:
            if vendor_category and not existing.category:
                existing.category = vendor_category
            if contact_info:
                existing.contact_info = contact_info
            if vendor_notes:
                if existing.notes:
                    if vendor_notes not in existing.notes:
                        existing.notes = f"{existing.notes}\n{vendor_notes}"
                else:
                    existing.notes = vendor_notes
            await db.flush()
            return existing.id

        new_vendor = Vendor(
            event_id=event_id,
            name=vendor_name,
            category=vendor_category or "other",
            contact_info=contact_info,
            notes=vendor_notes,
        )
        db.add(new_vendor)
        await db.flush()
        return new_vendor.id

    async def _update_vendor_by_name(
        self,
        event_id: str,
        data: dict,
        db: AsyncSession,
    ) -> Optional[str]:
        """Update a vendor record found by name. Returns vendor ID or None if not found."""
        vendor_name = data.get("name")
        if not vendor_name:
            return None

        existing = await self._find_vendor_by_name(event_id, vendor_name, db)
        if not existing:
            return None

        if data.get("notes"):
            if existing.notes:
                if data["notes"] not in existing.notes:
                    existing.notes = f"{existing.notes}\n{data['notes']}"
            else:
                existing.notes = data["notes"]
        if data.get("contact_info"):
            existing.contact_info = data["contact_info"]
        if data.get("category"):
            existing.category = data["category"]

        await db.commit()
        await db.refresh(existing)
        return existing.id
    
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

    async def _find_and_update_payment(
        self,
        event_id: str,
        data: dict,
        db: AsyncSession,
    ) -> bool:
        """Find an existing payment by vendor name + amount and update its metadata (method, notes)."""
        vendor_name = data.get("vendor_name")
        raw_amount = data.get("amount_paid") or data.get("amount") or 0
        try:
            target_amount = float(str(raw_amount))
        except (ValueError, TypeError):
            target_amount = 0

        if not vendor_name or target_amount <= 0:
            return False

        vendor = await self._find_vendor_by_name(event_id, vendor_name, db)
        if not vendor:
            return False

        result = await db.execute(
            select(Payment).where(
                Payment.event_id == event_id,
                Payment.vendor_id == vendor.id,
                Payment.amount == target_amount,
            )
        )
        payment = result.scalars().first()
        if not payment:
            return False

        if data.get("method"):
            payment.method = data["method"]
        if data.get("notes"):
            existing_notes = payment.notes or ""
            new_note = data["notes"]
            if new_note not in existing_notes:
                payment.notes = f"{existing_notes}; {new_note}".strip("; ")
        if data.get("payment_date") and not payment.paid_date:
            if isinstance(data["payment_date"], str):
                payment.paid_date = date.fromisoformat(data["payment_date"])
            else:
                payment.paid_date = data["payment_date"]

        await db.commit()
        return True

    def _infer_vendor_category(self, vendor_name: str) -> str | None:
        """Infer vendor category from common vendor type names."""
        if not vendor_name:
            return None
        name_lower = vendor_name.lower()
        category_map = {
            # Photography
            "photographer": "photography",
            "photography": "photography",
            "photo": "photography",
            "candid": "photography",
            # Videography
            "videographer": "videography",
            "videography": "videography",
            "video": "videography",
            "film": "videography",
            "cinemat": "videography",
            # Catering
            "caterer": "catering",
            "catering": "catering",
            "food": "catering",
            "chaat": "catering",
            "halwai": "catering",
            "cook": "catering",
            # Florist
            "florist": "florist",
            "flowers": "florist",
            "floral": "florist",
            "garland": "florist",
            "varmala": "florist",
            "phool": "florist",
            # Music & DJ
            "dj": "music_dj",
            "band": "music_dj",
            "musician": "music_dj",
            "dhol": "music_dj",
            "orchestra": "music_dj",
            "anchor": "music_dj",
            "emcee": "music_dj",
            "sangeet": "music_dj",
            # Decor
            "decorator": "decor",
            "decor": "decor",
            "mandap": "decor",
            "stage": "decor",
            "lighting": "decor",
            # Makeup & Hair
            "makeup": "makeup_hair",
            "hair": "makeup_hair",
            "mua": "makeup_hair",
            "bridal look": "makeup_hair",
            "stylist": "makeup_hair",
            # Mehndi
            "mehndi": "mehndi",
            "henna": "mehndi",
            "mehendi": "mehndi",
            # Officiant
            "officiant": "officiant",
            "minister": "officiant",
            "priest": "officiant",
            "pastor": "officiant",
            "rabbi": "officiant",
            "pandit": "officiant",
            "purohit": "officiant",
            "pujari": "officiant",
            # Transportation
            "transportation": "transportation",
            "limo": "transportation",
            "doli": "transportation",
            "palki": "transportation",
            "ghodi": "transportation",
            "baraat": "transportation",
            # Rentals
            "rental": "rentals",
            "rentals": "rentals",
            "tent": "rentals",
            "shamiyana": "rentals",
            "crockery": "rentals",
            # Bakery
            "baker": "bakery",
            "bakery": "bakery",
            "cake": "bakery",
            "dessert": "bakery",
            "mithai": "bakery",
            "sweet": "bakery",
            # Invitations
            "invitation": "invitations",
            "stationery": "invitations",
            "card": "invitations",
            # Venue
            "venue": "venue",
            "hall": "venue",
            "ballroom": "venue",
            "resort": "venue",
            "farmhouse": "venue",
            "palace": "venue",
            "lawn": "venue",
            "banquet": "venue",
            # Attire
            "lehenga": "attire",
            "saree": "attire",
            "sherwani": "attire",
            "boutique": "attire",
            "tailor": "attire",
            "bridal wear": "attire",
            "groom wear": "attire",
            # Jewelry
            "jewel": "jewelry",
            "kundan": "jewelry",
            "polki": "jewelry",
            "gold": "jewelry",
            # Choreographer
            "choreograph": "choreographer",
            "dance": "choreographer",
            # Planner
            "planner": "planner",
            "coordinator": "planner",
            "organizer": "planner",
            # Favors
            "favor": "favors",
            "gift": "favors",
            "trousseau": "favors",
            "return gift": "favors",
            # Travel
            "honeymoon": "travel",
            "travel": "travel",
        }
        for keyword, category in category_map.items():
            if keyword in name_lower:
                return category
        return None

    async def _create_payment(
        self,
        event_id: str,
        data: dict,
        db: AsyncSession,
    ) -> str:
        """Create a payment from extracted data."""
        vendor_id = None
        vendor_name = data.get("vendor_name")
        vendor_category = data.get("vendor_category")
        
        if not vendor_category and vendor_name:
            vendor_category = self._infer_vendor_category(vendor_name)
        
        vendor_notes = data.get("vendor_notes")
        
        if vendor_name:
            vendor_id = await self._resolve_or_create_vendor(
                event_id, vendor_name, vendor_category, vendor_notes, db
            )
            if vendor_id and not vendor_category:
                v_res = await db.execute(select(Vendor).where(Vendor.id == vendor_id))
                v_obj = v_res.scalar_one_or_none()
                if v_obj and v_obj.category:
                    vendor_category = v_obj.category
        
        raw_amount = data.get("amount_paid") or data.get("amount") or 0
        try:
            amount = Decimal(str(raw_amount))
        except Exception:
            amount = Decimal("0")
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
        elif data.get("paid_date"):
            if isinstance(data["paid_date"], str):
                paid_date = date.fromisoformat(data["paid_date"])
            else:
                paid_date = data["paid_date"]
        elif amount and amount > 0 and not due_date:
            paid_date = date.today()
        
        description = data.get("description") or ""
        if not description and vendor_name:
            description = f"Payment to {vendor_name}"
        
        primary_due_date = due_date if not paid_date else None

        remaining_amount = 0
        try:
            remaining_amount = float(remaining_balance) if remaining_balance else 0
        except (ValueError, TypeError):
            remaining_amount = 0

        skip_primary = (float(amount) == 0 and remaining_amount > 0)

        # Guard: never create a $0 payment record
        if float(amount) == 0 and remaining_amount == 0:
            await db.commit()
            return ""

        payment = None
        if not skip_primary:
            # Check for duplicate: same vendor, same amount, same paid_date
            if vendor_id and paid_date and float(amount) > 0:
                dup_check = await db.execute(
                    select(Payment).where(
                        Payment.event_id == event_id,
                        Payment.vendor_id == vendor_id,
                        Payment.amount == amount,
                        Payment.paid_date == paid_date,
                    )
                )
                existing_paid = dup_check.scalars().first()
                if existing_paid:
                    # Update metadata on existing instead of creating duplicate
                    if data.get("method") and not existing_paid.method:
                        existing_paid.method = data["method"]
                    if description and existing_paid.notes and description not in existing_paid.notes:
                        existing_paid.notes = f"{existing_paid.notes}; {description}"
                    await db.commit()
                    await db.refresh(existing_paid)
                    return existing_paid.id

            payment = Payment(
                event_id=event_id,
                vendor_id=vendor_id,
                amount=amount,
                paid_date=paid_date,
                due_date=primary_due_date,
                method=data.get("method"),
                notes=description,
            )
            db.add(payment)
            await db.flush()

            if primary_due_date and not paid_date and float(amount) > 0:
                await self._create_payment_reminder_task(
                    event_id=event_id,
                    vendor_name=vendor_name or "Vendor",
                    amount=float(amount),
                    due_date=primary_due_date,
                    db=db,
                    vendor_id=vendor_id,
                    vendor_category=vendor_category,
                )

        if remaining_amount > 0 and vendor_id:
            # Check if a pending payment for this vendor+amount already exists
            pending_dup = await db.execute(
                select(Payment).where(
                    Payment.event_id == event_id,
                    Payment.vendor_id == vendor_id,
                    Payment.amount == remaining_amount,
                    Payment.paid_date.is_(None),
                )
            )
            existing_pending = pending_dup.scalars().first()

            if not existing_pending:
                pending_due_date = due_date
                pending_payment = Payment(
                    event_id=event_id,
                    vendor_id=vendor_id,
                    amount=remaining_amount,
                    paid_date=None,
                    due_date=pending_due_date,
                    method=None,
                    notes=f"Remaining balance to {vendor_name or 'vendor'}",
                )
                db.add(pending_payment)

                if pending_due_date and remaining_amount > 0:
                    await self._create_payment_reminder_task(
                        event_id=event_id,
                        vendor_name=vendor_name or "Vendor",
                        amount=remaining_amount,
                        due_date=pending_due_date,
                        db=db,
                        vendor_id=vendor_id,
                        vendor_category=vendor_category,
                    )

                if not payment:
                    payment = pending_payment

        await db.commit()
        if payment:
            await db.refresh(payment)
        
        return payment.id if payment else ""
    
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
            vendor_category=data.get("vendor_category"),
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)
        return task.id
    
    async def _update_task_by_id(
        self,
        task_id: str,
        data: dict,
        db: AsyncSession,
    ) -> str:
        """Update an existing task's fields."""
        from app.models.task import TaskPriority
        
        result = await db.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        if "title" in data and data["title"]:
            task.title = data["title"]
        if "description" in data and data["description"] is not None:
            task.description = data["description"]
        if "due_date" in data:
            dd = data["due_date"]
            if isinstance(dd, str):
                dd = date.fromisoformat(dd)
            task.due_date = dd
        if "priority" in data:
            priority_map = {
                "low": TaskPriority.LOW,
                "medium": TaskPriority.MEDIUM,
                "high": TaskPriority.HIGH,
            }
            task.priority = priority_map.get(data["priority"], task.priority)
        if "vendor_category" in data:
            task.vendor_category = data["vendor_category"]
        
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
        vendor_id: str | None = None,
        vendor_category: str | None = None,
    ) -> str:
        """Auto-create a task to remind about an upcoming payment, unless one already exists."""
        from app.models.task import TaskStatus, TaskPriority

        expected_title = f"Payment due: ${amount:,.0f} to {vendor_name}"
        dup = await db.execute(
            select(Task).where(
                Task.event_id == event_id,
                Task.title == expected_title,
                Task.status == TaskStatus.PENDING,
            )
        )
        if dup.scalars().first():
            return ""

        task = Task(
            event_id=event_id,
            vendor_id=vendor_id,
            vendor_category=vendor_category,
            title=expected_title,
            description=f"Reminder: ${amount:,.2f} payment due to {vendor_name}",
            due_date=due_date,
            status=TaskStatus.PENDING,
            priority=TaskPriority.HIGH,
        )
        db.add(task)
        await db.flush()
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
        """Create or update a vendor. Always checks for duplicates first."""
        vendor_id = await self._resolve_or_create_vendor(
            event_id=event_id,
            vendor_name=data.get("name", "Unknown Vendor"),
            vendor_category=data.get("category"),
            vendor_notes=data.get("notes"),
            db=db,
            contact_info=data.get("contact_info"),
        )
        await db.commit()
        return vendor_id
    
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
        if data.get("event_date"):
            event_date_val = data["event_date"]
            if isinstance(event_date_val, str):
                event_date_val = date.fromisoformat(event_date_val)
            event.event_date = event_date_val
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
    
    async def handle_query(
        self,
        event_id: str,
        data: dict,
        db: AsyncSession,
    ) -> dict:
        """
        Handle a query intent and return results with natural language response.
        
        Args:
            event_id: The event ID
            data: The query data from LLM extraction
            db: Database session
        
        Returns:
            Dict with query_type, results, and natural_response
        """
        query_type = data.get("query_type", "list")
        target = data.get("target", "all")
        filters = data.get("filters", {})
        sort_by = data.get("sort_by")
        sort_order = data.get("sort_order", "desc")
        limit = data.get("limit")
        
        results = {}
        
        if target in ["payments", "all"]:
            payments = await self._query_payments(event_id, filters, sort_by, sort_order, limit, db)
            results["payments"] = payments
        
        if target in ["tasks", "all"]:
            tasks = await self._query_tasks(event_id, filters, sort_by, sort_order, limit, db)
            results["tasks"] = tasks
        
        if target in ["vendors", "all"]:
            vendors = await self._query_vendors(event_id, filters, limit, db)
            results["vendors"] = vendors
        
        if target in ["calendar_events", "all"]:
            events = await self._query_calendar_events(event_id, filters, sort_by, sort_order, limit, db)
            results["calendar_events"] = events
        
        natural_response = self._generate_query_response(query_type, target, results, filters)
        
        return {
            "query_type": query_type,
            "target": target,
            "results": results,
            "natural_response": natural_response,
        }
    
    async def _query_payments(
        self,
        event_id: str,
        filters: dict,
        sort_by: Optional[str],
        sort_order: str,
        limit: Optional[int],
        db: AsyncSession,
    ) -> list[dict]:
        """Query payments with filters."""
        query = select(Payment).where(Payment.event_id == event_id)
        
        if filters.get("vendor_name"):
            vendor = await self._find_vendor_by_name(event_id, filters["vendor_name"], db)
            if vendor:
                query = query.where(Payment.vendor_id == vendor.id)
        
        if filters.get("status") == "pending":
            query = query.where(Payment.due_date.isnot(None))
        
        if sort_by == "amount":
            query = query.order_by(desc(Payment.amount) if sort_order == "desc" else asc(Payment.amount))
        elif sort_by == "date":
            query = query.order_by(desc(Payment.paid_date) if sort_order == "desc" else asc(Payment.paid_date))
        else:
            query = query.order_by(desc(Payment.created_at))
        
        if limit:
            query = query.limit(limit)
        
        result = await db.execute(query)
        payments = result.scalars().all()
        
        payment_list = []
        for p in payments:
            vendor_name = None
            if p.vendor_id:
                v_result = await db.execute(select(Vendor).where(Vendor.id == p.vendor_id))
                vendor = v_result.scalar_one_or_none()
                vendor_name = vendor.name if vendor else None
            
            payment_list.append({
                "id": p.id,
                "amount": float(p.amount) if p.amount else 0,
                "vendor_name": vendor_name,
                "paid_date": p.paid_date.isoformat() if p.paid_date else None,
                "due_date": p.due_date.isoformat() if p.due_date else None,
                "method": p.method,
                "notes": p.notes,
            })
        
        return payment_list
    
    async def _query_tasks(
        self,
        event_id: str,
        filters: dict,
        sort_by: Optional[str],
        sort_order: str,
        limit: Optional[int],
        db: AsyncSession,
    ) -> list[dict]:
        """Query tasks with filters."""
        query = select(Task).where(Task.event_id == event_id)
        
        if filters.get("status"):
            status_val = filters["status"].upper()
            if hasattr(TaskStatus, status_val):
                query = query.where(Task.status == TaskStatus[status_val])
        
        if filters.get("due_date_range") == "this_week":
            today = date.today()
            week_end = today + timedelta(days=7)
            query = query.where(Task.due_date >= today, Task.due_date <= week_end)
        
        if sort_by == "due_date":
            query = query.order_by(desc(Task.due_date) if sort_order == "desc" else asc(Task.due_date))
        else:
            query = query.order_by(asc(Task.due_date))
        
        if limit:
            query = query.limit(limit)
        
        result = await db.execute(query)
        tasks = result.scalars().all()
        
        return [
            {
                "id": t.id,
                "title": t.title,
                "description": t.description,
                "due_date": t.due_date.isoformat() if t.due_date else None,
                "status": t.status.value if t.status else None,
                "priority": t.priority.value if t.priority else None,
            }
            for t in tasks
        ]
    
    async def _query_vendors(
        self,
        event_id: str,
        filters: dict,
        limit: Optional[int],
        db: AsyncSession,
    ) -> list[dict]:
        """Query vendors with filters."""
        query = select(Vendor).where(Vendor.event_id == event_id)
        
        if filters.get("category"):
            query = query.where(Vendor.category.ilike(f"%{filters['category']}%"))
        
        query = query.order_by(Vendor.name)
        
        if limit:
            query = query.limit(limit)
        
        result = await db.execute(query)
        vendors = result.scalars().all()
        
        return [
            {
                "id": v.id,
                "name": v.name,
                "category": v.category,
                "contact_info": v.contact_info,
                "notes": v.notes,
            }
            for v in vendors
        ]
    
    async def _query_calendar_events(
        self,
        event_id: str,
        filters: dict,
        sort_by: Optional[str],
        sort_order: str,
        limit: Optional[int],
        db: AsyncSession,
    ) -> list[dict]:
        """Query calendar events with filters."""
        query = select(CalendarEvent).where(CalendarEvent.event_id == event_id)
        
        if filters.get("upcoming"):
            query = query.where(CalendarEvent.event_date >= date.today())
        
        if filters.get("due_date_range") == "this_week":
            today = date.today()
            week_end = today + timedelta(days=7)
            query = query.where(CalendarEvent.event_date >= today, CalendarEvent.event_date <= week_end)
        
        if sort_by == "date":
            query = query.order_by(desc(CalendarEvent.event_date) if sort_order == "desc" else asc(CalendarEvent.event_date))
        else:
            query = query.order_by(asc(CalendarEvent.event_date))
        
        if limit:
            query = query.limit(limit)
        
        result = await db.execute(query)
        events = result.scalars().all()
        
        return [
            {
                "id": e.id,
                "title": e.title,
                "event_date": e.event_date.isoformat() if e.event_date else None,
                "event_time": e.event_time.strftime("%H:%M") if e.event_time else None,
                "location": e.location,
                "notes": e.notes,
            }
            for e in events
        ]
    
    def _generate_query_response(
        self,
        query_type: str,
        target: str,
        results: dict,
        filters: dict,
    ) -> str:
        """Generate a natural language response for the query results."""
        total_items = sum(len(items) for items in results.values())
        
        if total_items == 0:
            if target == "payments":
                return "I couldn't find any payments matching your criteria."
            elif target == "tasks":
                return "No tasks found matching your criteria."
            elif target == "vendors":
                return "No vendors found."
            elif target == "calendar_events":
                return "No upcoming events found."
            return "I couldn't find any matching records."
        
        response_parts = []
        
        if "payments" in results and results["payments"]:
            payments = results["payments"]
            total_amount = sum(p.get("amount", 0) for p in payments)
            
            if query_type == "aggregate" and len(payments) == 1:
                p = payments[0]
                vendor = p.get("vendor_name") or "Unknown vendor"
                amount = p.get("amount", 0)
                response_parts.append(f"Your largest expense is ${amount:,.2f} to {vendor}.")
            else:
                response_parts.append(f"Found {len(payments)} payment(s) totaling ${total_amount:,.2f}.")
        
        if "tasks" in results and results["tasks"]:
            tasks = results["tasks"]
            pending = sum(1 for t in tasks if t.get("status") == "pending")
            if pending > 0:
                response_parts.append(f"You have {pending} pending task(s).")
            else:
                response_parts.append(f"Found {len(tasks)} task(s).")
        
        if "vendors" in results and results["vendors"]:
            vendors = results["vendors"]
            response_parts.append(f"Found {len(vendors)} vendor(s).")
        
        if "calendar_events" in results and results["calendar_events"]:
            events = results["calendar_events"]
            response_parts.append(f"Found {len(events)} upcoming event(s).")
        
        return " ".join(response_parts)


def get_extraction_service() -> ExtractionService:
    """Get extraction service instance."""
    return ExtractionService()
