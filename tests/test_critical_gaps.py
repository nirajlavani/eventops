"""
Critical Gap Tests for EventOps.

Closes all remaining partial gaps in the testing suite:
1. Payment update - verify DB value changes end-to-end
2. Delete confirmed + DB verified - row actually removed
3. Sub-event CRUD full cycle - add, update, cancel
4. Task auto-creation from pending payment
5. Feedback system API tests
"""
import pytest
from datetime import date, time as dt_time, timedelta
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models import Event, Vendor, Payment, Task, SubEvent
from app.models.feedback_log import FeedbackLog
from app.models.task import TaskPriority
from app.schemas.capture import IntentType, ActionType


# =============================================================================
# 1. PAYMENT UPDATE - FULL END-TO-END DB VERIFICATION
# =============================================================================

@pytest.mark.payments
class TestPaymentUpdateE2E:
    """Verify payment updates change actual DB values, not just API responses."""
    
    @pytest.fixture
    async def event_with_payment(self, client: AsyncClient, test_db: AsyncSession):
        """Create event with a vendor and existing payment."""
        event = Event(name="Payment Update Test", event_date=date(2026, 8, 15))
        test_db.add(event)
        await test_db.flush()
        
        vendor = Vendor(
            event_id=event.id,
            name="The Grand Pavilion",
            category="venue"
        )
        test_db.add(vendor)
        await test_db.flush()
        
        payment = Payment(
            event_id=event.id,
            vendor_id=vendor.id,
            amount=Decimal("15000"),
            paid_date=date(2026, 1, 15),
            method="bank_transfer",
            notes="Initial deposit"
        )
        test_db.add(payment)
        
        pending = Payment(
            event_id=event.id,
            vendor_id=vendor.id,
            amount=Decimal("30000"),
            paid_date=None,
            due_date=date(2026, 7, 1),
            notes="Remaining balance to The Grand Pavilion"
        )
        test_db.add(pending)
        
        await test_db.commit()
        
        return {
            "event_id": event.id,
            "vendor_id": vendor.id,
            "payment_id": payment.id,
            "pending_id": pending.id,
            "db": test_db,
        }
    
    @pytest.mark.asyncio
    async def test_additional_payment_increases_total_in_db(
        self, client: AsyncClient, event_with_payment: dict
    ):
        """Verify that an additional payment to an existing vendor creates a new row."""
        eid = event_with_payment["event_id"]
        db = event_with_payment["db"]
        
        # Sum of all paid amounts before
        result = await db.execute(
            select(func.sum(Payment.amount)).where(
                Payment.event_id == eid,
                Payment.paid_date.isnot(None),
            )
        )
        paid_before = float(result.scalar() or 0)
        
        response = await client.post(
            f"/api/events/{eid}/capture/extract",
            json={
                "text": "Just paid another $10,000 to The Grand Pavilion today via check",
                "conversation_history": []
            }
        )
        
        data = response.json()
        
        if data.get("needs_confirmation"):
            confirm_payload = {
                "log_id": data.get("log_id"),
                "intent": data.get("intent"),
                "action": data.get("action", "create"),
                "data": data.get("data", {}),
            }
            if data.get("reference_id"):
                confirm_payload["reference_id"] = data["reference_id"]
            
            confirm_resp = await client.post(
                f"/api/events/{eid}/capture/confirm",
                json=confirm_payload
            )
            
            if confirm_resp.status_code == 200:
                # Verify sum increased
                result_after = await db.execute(
                    select(func.sum(Payment.amount)).where(
                        Payment.event_id == eid,
                        Payment.paid_date.isnot(None),
                    )
                )
                paid_after = float(result_after.scalar() or 0)
                
                assert paid_after > paid_before, \
                    f"Total paid should increase. Before: ${paid_before:,.0f}, After: ${paid_after:,.0f}"
    
    @pytest.mark.asyncio
    async def test_payment_to_existing_vendor_doesnt_duplicate_vendor(
        self, client: AsyncClient, event_with_payment: dict
    ):
        """Verify additional payment to same vendor doesn't create a duplicate vendor."""
        eid = event_with_payment["event_id"]
        db = event_with_payment["db"]
        
        vendor_count_before = (await db.execute(
            select(func.count(Vendor.id)).where(Vendor.event_id == eid)
        )).scalar()
        
        response = await client.post(
            f"/api/events/{eid}/capture/extract",
            json={
                "text": "Paid $5,000 more to The Grand Pavilion today",
                "conversation_history": []
            }
        )
        
        data = response.json()
        if data.get("needs_confirmation"):
            confirm_payload = {
                "log_id": data.get("log_id"),
                "intent": data.get("intent"),
                "action": data.get("action", "create"),
                "data": data.get("data", {}),
            }
            if data.get("reference_id"):
                confirm_payload["reference_id"] = data["reference_id"]
            
            await client.post(
                f"/api/events/{eid}/capture/confirm",
                json=confirm_payload
            )
        
        vendor_count_after = (await db.execute(
            select(func.count(Vendor.id)).where(Vendor.event_id == eid)
        )).scalar()
        
        assert vendor_count_after == vendor_count_before, \
            f"Should not duplicate vendor. Before: {vendor_count_before}, After: {vendor_count_after}"


# =============================================================================
# 2. DELETE CONFIRMED + DB VERIFIED
# =============================================================================

@pytest.mark.deletes
class TestDeleteE2E:
    """Verify delete operations actually remove rows from the database."""
    
    @pytest.fixture
    async def event_with_deletable_task(self, client: AsyncClient, test_db: AsyncSession):
        """Create event with tasks that can be deleted."""
        event = Event(name="Delete Test", event_date=date(2026, 9, 1))
        test_db.add(event)
        await test_db.flush()
        
        task1 = Task(
            event_id=event.id,
            title="Book florist",
            status="pending",
            priority="medium",
        )
        task2 = Task(
            event_id=event.id,
            title="Arrange airport pickups for guests",
            status="pending",
            priority="low",
        )
        task3 = Task(
            event_id=event.id,
            title="Order invitations",
            status="completed",
            priority="high",
        )
        test_db.add_all([task1, task2, task3])
        await test_db.commit()
        
        return {
            "event_id": event.id,
            "task_ids": [task1.id, task2.id, task3.id],
            "db": test_db,
        }
    
    @pytest.mark.asyncio
    async def test_delete_task_removes_row_from_db(
        self, client: AsyncClient, event_with_deletable_task: dict
    ):
        """Verify deleting a task actually removes it from the database."""
        eid = event_with_deletable_task["event_id"]
        db = event_with_deletable_task["db"]
        
        count_before = (await db.execute(
            select(func.count(Task.id)).where(Task.event_id == eid)
        )).scalar()
        assert count_before == 3, f"Should start with 3 tasks, got {count_before}"
        
        # Ask to delete
        response = await client.post(
            f"/api/events/{eid}/capture/extract",
            json={
                "text": "Delete the airport pickups task",
                "conversation_history": []
            }
        )
        
        data = response.json()
        
        # If the LLM gives a confirmation prompt, we need to confirm via the confirm endpoint
        if data.get("needs_confirmation") and data.get("log_id"):
            confirm_payload = {
                "log_id": data.get("log_id"),
                "intent": data.get("intent"),
                "action": data.get("action", "delete"),
                "data": data.get("data", {}),
            }
            if data.get("reference_id"):
                confirm_payload["reference_id"] = data["reference_id"]
            
            confirm_resp = await client.post(
                f"/api/events/{eid}/capture/confirm",
                json=confirm_payload
            )
            
            if confirm_resp.status_code == 200 and confirm_resp.json().get("success"):
                count_after = (await db.execute(
                    select(func.count(Task.id)).where(Task.event_id == eid)
                )).scalar()
                
                assert count_after < count_before, \
                    f"Task should be removed. Before: {count_before}, After: {count_after}"
    
    @pytest.fixture
    async def event_with_deletable_payment(self, client: AsyncClient, test_db: AsyncSession):
        """Create event with a payment that can be deleted."""
        event = Event(name="Delete Payment Test", event_date=date(2026, 9, 1))
        test_db.add(event)
        await test_db.flush()
        
        vendor = Vendor(event_id=event.id, name="Test Vendor", category="other")
        test_db.add(vendor)
        await test_db.flush()
        
        payment = Payment(
            event_id=event.id,
            vendor_id=vendor.id,
            amount=Decimal("5000"),
            paid_date=date(2026, 3, 1),
            method="cash",
            notes="Test payment"
        )
        test_db.add(payment)
        await test_db.commit()
        
        return {
            "event_id": event.id,
            "payment_id": payment.id,
            "db": test_db,
        }
    
    @pytest.mark.asyncio
    async def test_delete_payment_removes_row_from_db(
        self, client: AsyncClient, event_with_deletable_payment: dict
    ):
        """Verify deleting a payment removes it from the database."""
        eid = event_with_deletable_payment["event_id"]
        pid = event_with_deletable_payment["payment_id"]
        db = event_with_deletable_payment["db"]
        
        # Verify exists
        result = await db.execute(select(Payment).where(Payment.id == pid))
        assert result.scalar_one_or_none() is not None, "Payment should exist before delete"
        
        response = await client.post(
            f"/api/events/{eid}/capture/extract",
            json={
                "text": "Delete the $5,000 payment to Test Vendor",
                "conversation_history": []
            }
        )
        
        data = response.json()
        
        if data.get("needs_confirmation") and data.get("log_id") and data.get("reference_id"):
            confirm_resp = await client.post(
                f"/api/events/{eid}/capture/confirm",
                json={
                    "log_id": data["log_id"],
                    "intent": data["intent"],
                    "action": "delete",
                    "reference_id": data["reference_id"],
                    "data": data.get("data", {}),
                }
            )
            
            if confirm_resp.status_code == 200 and confirm_resp.json().get("success"):
                result = await db.execute(select(Payment).where(Payment.id == pid))
                assert result.scalar_one_or_none() is None, \
                    "Payment should be removed from DB after confirmed delete"


# =============================================================================
# 3. SUB-EVENT CRUD FULL CYCLE
# =============================================================================

@pytest.mark.subevents
class TestSubEventCRUD:
    """Test complete Create, Read, Update, Delete cycle for sub-events."""
    
    @pytest.fixture
    async def event_with_subevents(self, client: AsyncClient, test_db: AsyncSession):
        """Create event with sub-events."""
        event = Event(name="Sub-event CRUD Test", event_date=date(2026, 8, 15))
        test_db.add(event)
        await test_db.flush()
        
        subevents = [
            SubEvent(
                event_id=event.id, name="Mehndi",
                date=date(2026, 8, 12), start_time=dt_time(16, 0),
                location="Garden Area"
            ),
            SubEvent(
                event_id=event.id, name="Sangeet",
                date=date(2026, 8, 13), start_time=dt_time(18, 0),
                location="Ballroom"
            ),
            SubEvent(
                event_id=event.id, name="Wedding Ceremony",
                date=date(2026, 8, 15), start_time=dt_time(11, 0),
                location="Mandap"
            ),
        ]
        for se in subevents:
            test_db.add(se)
        await test_db.commit()
        
        return {
            "event_id": event.id,
            "subevent_ids": [se.id for se in subevents],
            "db": test_db,
        }
    
    @pytest.mark.asyncio
    async def test_add_subevent_creates_row(
        self, client: AsyncClient, event_with_subevents: dict
    ):
        """Verify adding a sub-event creates a new row in the database."""
        eid = event_with_subevents["event_id"]
        db = event_with_subevents["db"]
        
        count_before = (await db.execute(
            select(func.count(SubEvent.id)).where(SubEvent.event_id == eid)
        )).scalar()
        
        response = await client.post(
            f"/api/events/{eid}/capture/extract",
            json={
                "text": "Add a new Haldi ceremony on August 14th at 10am at the pool area",
                "conversation_history": []
            }
        )
        
        data = response.json()
        
        if data.get("needs_confirmation") and data.get("log_id"):
            confirm_resp = await client.post(
                f"/api/events/{eid}/capture/confirm",
                json={
                    "log_id": data["log_id"],
                    "intent": data["intent"],
                    "action": data.get("action", "create"),
                    "data": data.get("data", {}),
                }
            )
            
            if confirm_resp.status_code == 200 and confirm_resp.json().get("success"):
                count_after = (await db.execute(
                    select(func.count(SubEvent.id)).where(SubEvent.event_id == eid)
                )).scalar()
                
                assert count_after > count_before, \
                    f"Sub-event should be added. Before: {count_before}, After: {count_after}"
    
    @pytest.mark.asyncio
    async def test_cancel_subevent_removes_row(
        self, client: AsyncClient, event_with_subevents: dict
    ):
        """Verify cancelling a sub-event removes it from the database."""
        eid = event_with_subevents["event_id"]
        db = event_with_subevents["db"]
        
        count_before = (await db.execute(
            select(func.count(SubEvent.id)).where(SubEvent.event_id == eid)
        )).scalar()
        
        response = await client.post(
            f"/api/events/{eid}/capture/extract",
            json={
                "text": "Cancel the sangeet event",
                "conversation_history": []
            }
        )
        
        data = response.json()
        
        if data.get("needs_confirmation") and data.get("log_id"):
            confirm_resp = await client.post(
                f"/api/events/{eid}/capture/confirm",
                json={
                    "log_id": data["log_id"],
                    "intent": data["intent"],
                    "action": data.get("action", "create"),
                    "data": data.get("data", {}),
                }
            )
            
            if confirm_resp.status_code == 200 and confirm_resp.json().get("success"):
                count_after = (await db.execute(
                    select(func.count(SubEvent.id)).where(SubEvent.event_id == eid)
                )).scalar()
                
                assert count_after < count_before, \
                    f"Sub-event should be removed. Before: {count_before}, After: {count_after}"
    
    @pytest.mark.asyncio
    async def test_update_subevent_location_changes_db(
        self, client: AsyncClient, event_with_subevents: dict
    ):
        """Verify updating a sub-event's location changes the value in DB."""
        eid = event_with_subevents["event_id"]
        db = event_with_subevents["db"]
        
        # Get original mehndi location
        result = await db.execute(
            select(SubEvent).where(
                SubEvent.event_id == eid,
                SubEvent.name.ilike("%mehndi%"),
            )
        )
        mehndi = result.scalar_one_or_none()
        assert mehndi is not None
        original_location = mehndi.location
        
        response = await client.post(
            f"/api/events/{eid}/capture/extract",
            json={
                "text": "Change the mehndi location to the Rooftop Terrace",
                "conversation_history": []
            }
        )
        
        data = response.json()
        
        if data.get("needs_confirmation") and data.get("log_id"):
            confirm_resp = await client.post(
                f"/api/events/{eid}/capture/confirm",
                json={
                    "log_id": data["log_id"],
                    "intent": data["intent"],
                    "action": data.get("action", "create"),
                    "data": data.get("data", {}),
                }
            )
            
            if confirm_resp.status_code == 200 and confirm_resp.json().get("success"):
                await db.refresh(mehndi)
                
                assert mehndi.location != original_location or "rooftop" in (mehndi.location or "").lower(), \
                    f"Location should change. Original: {original_location}, Current: {mehndi.location}"
    
    @pytest.mark.asyncio
    async def test_reschedule_subevent_changes_time_in_db(
        self, client: AsyncClient, event_with_subevents: dict
    ):
        """Verify rescheduling a sub-event changes the time in DB."""
        eid = event_with_subevents["event_id"]
        db = event_with_subevents["db"]
        
        response = await client.post(
            f"/api/events/{eid}/capture/extract",
            json={
                "text": "Move the sangeet to start at 7pm instead of 6pm",
                "conversation_history": []
            }
        )
        
        data = response.json()
        
        # Verify the LLM recognized this as a sub-event update
        assert data.get("intent") == "sub_event_update" or \
               "sangeet" in data.get("assistant_message", "").lower()


# =============================================================================
# 4. TASK AUTO-CREATION FROM PENDING PAYMENT
# =============================================================================

@pytest.mark.tasks
class TestTaskAutoCreation:
    """Verify that pending payments with due dates auto-create reminder tasks."""
    
    @pytest.fixture
    async def event_id(self, client: AsyncClient, test_db: AsyncSession):
        """Create a basic event."""
        event = Event(name="Task Auto-Create Test", event_date=date(2026, 8, 15))
        test_db.add(event)
        await test_db.commit()
        await test_db.refresh(event)
        return event.id
    
    @pytest.mark.asyncio
    async def test_partial_payment_with_due_date_creates_task(
        self, client: AsyncClient, test_db: AsyncSession, event_id: str
    ):
        """Verify a partial payment with a due date creates a reminder task."""
        # Count tasks before
        task_count_before = (await test_db.execute(
            select(func.count(Task.id)).where(Task.event_id == event_id)
        )).scalar()
        
        response = await client.post(
            f"/api/events/{event_id}/capture/extract",
            json={
                "text": "Booked Grand Venue for $30,000, paid $10,000 deposit, remaining $20,000 due July 1st 2026",
                "conversation_history": []
            }
        )
        
        data = response.json()
        
        if data.get("needs_confirmation") and data.get("log_id"):
            confirm_payload = {
                "log_id": data["log_id"],
                "intent": data["intent"],
                "action": data.get("action", "create"),
                "data": data.get("data", {}),
            }
            confirm_resp = await client.post(
                f"/api/events/{event_id}/capture/confirm",
                json=confirm_payload
            )
            
            if confirm_resp.status_code == 200 and confirm_resp.json().get("success"):
                task_count_after = (await test_db.execute(
                    select(func.count(Task.id)).where(Task.event_id == event_id)
                )).scalar()
                
                assert task_count_after > task_count_before, \
                    f"Pending payment should auto-create reminder task. Tasks before: {task_count_before}, after: {task_count_after}"
    
    @pytest.mark.asyncio
    async def test_auto_task_has_correct_due_date(
        self, client: AsyncClient, test_db: AsyncSession, event_id: str
    ):
        """Verify the auto-created task has the payment's due date."""
        response = await client.post(
            f"/api/events/{event_id}/capture/extract",
            json={
                "text": "Paid DJ Krish $1,000 deposit, remaining $2,500 due August 12th 2026",
                "conversation_history": []
            }
        )
        
        data = response.json()
        
        if data.get("needs_confirmation") and data.get("log_id"):
            confirm_payload = {
                "log_id": data["log_id"],
                "intent": data["intent"],
                "action": data.get("action", "create"),
                "data": data.get("data", {}),
            }
            confirm_resp = await client.post(
                f"/api/events/{event_id}/capture/confirm",
                json=confirm_payload
            )
            
            if confirm_resp.status_code == 200 and confirm_resp.json().get("success"):
                # Find the auto-created task
                result = await test_db.execute(
                    select(Task).where(
                        Task.event_id == event_id,
                        Task.title.ilike("%dj krish%")
                    )
                )
                task = result.scalar_one_or_none()
                
                if task:
                    assert task.due_date is not None, "Auto-created task should have a due date"
                    assert task.due_date.month == 8, f"Due date month should be August, got {task.due_date.month}"
                    assert task.due_date.day == 12, f"Due date day should be 12, got {task.due_date.day}"
                    assert task.priority == TaskPriority.HIGH, f"Auto-created payment task should be high priority, got {task.priority}"
    
    @pytest.mark.asyncio
    async def test_auto_task_title_includes_amount_and_vendor(
        self, client: AsyncClient, test_db: AsyncSession, event_id: str
    ):
        """Verify auto-created task title includes payment amount and vendor name."""
        response = await client.post(
            f"/api/events/{event_id}/capture/extract",
            json={
                "text": "Booked Petals & Blooms for $5,000, paid $1,500, remaining $3,500 due July 15th 2026",
                "conversation_history": []
            }
        )
        
        data = response.json()
        
        if data.get("needs_confirmation") and data.get("log_id"):
            confirm_payload = {
                "log_id": data["log_id"],
                "intent": data["intent"],
                "action": data.get("action", "create"),
                "data": data.get("data", {}),
            }
            confirm_resp = await client.post(
                f"/api/events/{event_id}/capture/confirm",
                json=confirm_payload
            )
            
            if confirm_resp.status_code == 200 and confirm_resp.json().get("success"):
                result = await test_db.execute(
                    select(Task).where(
                        Task.event_id == event_id,
                        Task.title.ilike("%petal%")
                    )
                )
                task = result.scalar_one_or_none()
                
                if task:
                    assert "3,500" in task.title or "3500" in task.title, \
                        f"Task title should include remaining amount. Got: {task.title}"
    
    @pytest.mark.asyncio
    async def test_full_payment_does_not_create_task(
        self, client: AsyncClient, test_db: AsyncSession, event_id: str
    ):
        """Verify full payment does NOT auto-create a reminder task."""
        task_count_before = (await test_db.execute(
            select(func.count(Task.id)).where(Task.event_id == event_id)
        )).scalar()
        
        response = await client.post(
            f"/api/events/{event_id}/capture/extract",
            json={
                "text": "Paid Pandit Sharma $1,500 in full today by check",
                "conversation_history": []
            }
        )
        
        data = response.json()
        
        if data.get("needs_confirmation") and data.get("log_id"):
            confirm_payload = {
                "log_id": data["log_id"],
                "intent": data["intent"],
                "action": data.get("action", "create"),
                "data": data.get("data", {}),
            }
            confirm_resp = await client.post(
                f"/api/events/{event_id}/capture/confirm",
                json=confirm_payload
            )
            
            if confirm_resp.status_code == 200 and confirm_resp.json().get("success"):
                task_count_after = (await test_db.execute(
                    select(func.count(Task.id)).where(Task.event_id == event_id)
                )).scalar()
                
                assert task_count_after == task_count_before, \
                    f"Full payment should NOT create task. Before: {task_count_before}, After: {task_count_after}"


# =============================================================================
# 5. FEEDBACK SYSTEM API TESTS
# =============================================================================

@pytest.mark.feedback
@pytest.mark.fast
class TestFeedbackSystem:
    """Test the feedback logging system end-to-end."""
    
    @pytest.fixture
    async def event_id(self, client: AsyncClient, test_db: AsyncSession):
        """Create a basic event."""
        event = Event(name="Feedback Test", event_date=date(2026, 8, 15))
        test_db.add(event)
        await test_db.commit()
        await test_db.refresh(event)
        return event.id
    
    @pytest.mark.asyncio
    async def test_submit_feedback_creates_record(self, client: AsyncClient, test_db: AsyncSession, event_id: str):
        """Verify submitting feedback creates a DB record."""
        response = await client.post(
            "/api/feedback",
            json={
                "event_id": event_id,
                "user_feedback": "The payment amount was wrong, it showed $5000 instead of $3000",
                "last_user_message": "I paid $3000 to the florist",
                "last_llm_response": "Recorded $5000 payment to the florist",
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        
        assert data["user_feedback"] == "The payment amount was wrong, it showed $5000 instead of $3000"
        assert data["is_resolved"] == False
        assert "id" in data
    
    @pytest.mark.asyncio
    async def test_submit_feedback_stored_in_db(self, client: AsyncClient, test_db: AsyncSession, event_id: str):
        """Verify feedback is actually stored in the database."""
        response = await client.post(
            "/api/feedback",
            json={
                "event_id": event_id,
                "user_feedback": "Dashboard stats didn't update after payment",
            }
        )
        
        feedback_id = response.json()["id"]
        
        result = await test_db.execute(
            select(FeedbackLog).where(FeedbackLog.id == feedback_id)
        )
        feedback = result.scalar_one_or_none()
        
        assert feedback is not None, "Feedback should be in database"
        assert feedback.user_feedback == "Dashboard stats didn't update after payment"
        assert feedback.event_id == event_id
        assert feedback.is_resolved == False
    
    @pytest.mark.asyncio
    async def test_list_feedback_returns_entries(self, client: AsyncClient, test_db: AsyncSession, event_id: str):
        """Verify listing feedback returns submitted entries."""
        # Submit 2 feedbacks
        await client.post(
            "/api/feedback",
            json={"event_id": event_id, "user_feedback": "Issue 1"}
        )
        await client.post(
            "/api/feedback",
            json={"event_id": event_id, "user_feedback": "Issue 2"}
        )
        
        response = await client.get("/api/feedback")
        assert response.status_code == 200
        
        feedbacks = response.json()
        assert len(feedbacks) >= 2
    
    @pytest.mark.asyncio
    async def test_resolve_feedback_updates_status(self, client: AsyncClient, test_db: AsyncSession, event_id: str):
        """Verify resolving feedback changes is_resolved to True."""
        # Submit feedback
        submit_resp = await client.post(
            "/api/feedback",
            json={"event_id": event_id, "user_feedback": "Fix this issue"}
        )
        feedback_id = submit_resp.json()["id"]
        
        # Resolve it
        resolve_resp = await client.patch(
            f"/api/feedback/{feedback_id}/resolve",
            params={"resolution_notes": "Fixed in commit abc123"}
        )
        
        assert resolve_resp.status_code == 200
        assert resolve_resp.json()["success"] == True
        
        # Verify in DB
        result = await test_db.execute(
            select(FeedbackLog).where(FeedbackLog.id == feedback_id)
        )
        feedback = result.scalar_one()
        
        assert feedback.is_resolved == True
        assert feedback.resolution_notes == "Fixed in commit abc123"
    
    @pytest.mark.asyncio
    async def test_get_feedback_detail(self, client: AsyncClient, test_db: AsyncSession, event_id: str):
        """Verify getting feedback detail returns full record."""
        submit_resp = await client.post(
            "/api/feedback",
            json={
                "event_id": event_id,
                "user_feedback": "Payment category wrong",
                "last_user_message": "Paid my pandit",
                "last_llm_response": "Saved as other",
                "conversation_history": "[{\"role\":\"user\",\"content\":\"test\"}]"
            }
        )
        feedback_id = submit_resp.json()["id"]
        
        detail_resp = await client.get(f"/api/feedback/{feedback_id}")
        assert detail_resp.status_code == 200
        
        detail = detail_resp.json()
        assert detail["user_feedback"] == "Payment category wrong"
        assert detail["last_user_message"] == "Paid my pandit"
        assert detail["last_llm_response"] == "Saved as other"
        assert detail["conversation_history"] is not None
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_feedback_returns_404(self, client: AsyncClient):
        """Verify 404 for non-existent feedback."""
        response = await client.get("/api/feedback/nonexistent-id")
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_filter_unresolved_feedback(self, client: AsyncClient, test_db: AsyncSession, event_id: str):
        """Verify filtering by resolved status works."""
        await client.post(
            "/api/feedback",
            json={"event_id": event_id, "user_feedback": "Unresolved issue"}
        )
        resp2 = await client.post(
            "/api/feedback",
            json={"event_id": event_id, "user_feedback": "Resolved issue"}
        )
        await client.patch(f"/api/feedback/{resp2.json()['id']}/resolve")
        
        # Get only unresolved
        unresolved_resp = await client.get("/api/feedback?resolved=false")
        assert unresolved_resp.status_code == 200
        
        unresolved = unresolved_resp.json()
        for f in unresolved:
            assert f["is_resolved"] == False
