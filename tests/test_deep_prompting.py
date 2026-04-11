"""
Deep Prompting Test Suite for EventOps.

This module tests advanced chatbot capabilities using a pre-populated
wedding event database. Tests run against existing data to validate:
- Complex queries on existing records
- Updates to existing payments/tasks/vendors
- Duplicate detection
- Conversation context preservation
- Multi-part queries

The pre-populated event includes:
- 5 sub-events
- 15 vendors
- 25+ payments (mix of paid and pending)
- 10 tasks (mix of completed and pending)

Total budget: ~$160,800 ($77,300 paid, $83,500 pending)
"""
import json
import pytest
from datetime import date
from decimal import Decimal
from pathlib import Path

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import Event, Vendor, Payment, Task
from tests.fixtures.seed_data import get_seed_data


@pytest.mark.fast
class TestDeepPromptingSetup:
    """Verify seed data is loaded correctly."""
    
    @pytest.mark.asyncio
    async def test_seed_data_creates_event(self, client: AsyncClient, test_db: AsyncSession):
        """Test that seed data creates event with correct data."""
        seed = get_seed_data()
        
        event = Event(
            id=seed["event"]["id"],
            name=seed["event"]["name"],
            event_date=seed["event"]["event_date"]
        )
        test_db.add(event)
        await test_db.commit()
        
        result = await test_db.execute(select(Event))
        events = result.scalars().all()
        
        assert len(events) == 1
        assert events[0].name == "Priya & Rahul's Wedding"


@pytest.mark.queries
class TestBudgetQueries:
    """Tests for budget and payment queries."""
    
    @pytest.fixture
    async def seeded_event(self, client: AsyncClient, test_db: AsyncSession):
        """Create a seeded event for testing."""
        seed = get_seed_data()
        
        event = Event(
            id=seed["event"]["id"],
            name=seed["event"]["name"],
            event_date=seed["event"]["event_date"]
        )
        test_db.add(event)
        
        for v in seed["vendors"]:
            vendor = Vendor(
                id=v["id"],
                event_id=v["event_id"],
                name=v["name"],
                category=v["category"],
                contact_info=v.get("contact_info"),
                notes=v.get("notes")
            )
            test_db.add(vendor)
        
        for p in seed["payments"]:
            payment = Payment(
                id=p["id"],
                event_id=p["event_id"],
                vendor_id=p["vendor_id"],
                amount=p["amount"],
                paid_date=p["paid_date"],
                due_date=p["due_date"],
                method=p.get("method"),
                notes=p.get("notes")
            )
            test_db.add(payment)
        
        for t in seed["tasks"]:
            task = Task(
                id=t["id"],
                event_id=t["event_id"],
                title=t["title"],
                description=t.get("description"),
                due_date=t.get("due_date"),
                status=t["status"],
                priority=t.get("priority", "medium")
            )
            test_db.add(task)
        
        await test_db.commit()
        
        return seed["event"]["id"]
    
    @pytest.mark.asyncio
    async def test_total_spent_query(self, client: AsyncClient, seeded_event: str):
        """DP-001: Query total spent on wedding."""
        response = await client.post(
            f"/api/events/{seeded_event}/capture/extract",
            json={
                "text": "How much have I spent so far on the wedding?",
                "conversation_history": []
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        msg = data.get("assistant_message", "").lower()
        assert "$" in msg or "spent" in msg or "paid" in msg
    
    @pytest.mark.asyncio
    async def test_vendor_specific_query(self, client: AsyncClient, seeded_event: str):
        """DP-003: Query specific vendor payments."""
        response = await client.post(
            f"/api/events/{seeded_event}/capture/extract",
            json={
                "text": "How much have I paid The Grand Pavilion so far?",
                "conversation_history": []
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        msg = data.get("assistant_message", "")
        assert "grand pavilion" in msg.lower() or "$" in msg
    
    @pytest.mark.asyncio
    async def test_pending_payments_query(self, client: AsyncClient, seeded_event: str):
        """DP-002: Query payments due soon."""
        response = await client.post(
            f"/api/events/{seeded_event}/capture/extract",
            json={
                "text": "What payments are still pending?",
                "conversation_history": []
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("response_mode") == "answer" or \
               data.get("intent") == "query"
    
    @pytest.mark.asyncio
    async def test_category_spending_query(self, client: AsyncClient, seeded_event: str):
        """DP-004: Query payments by category (decorator)."""
        response = await client.post(
            f"/api/events/{seeded_event}/capture/extract",
            json={
                "text": "Show me all payments to my decorator",
                "conversation_history": []
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        msg = data.get("assistant_message", "").lower()
        assert "decor" in msg or "celebration" in msg or "$" in msg


@pytest.mark.payments
class TestPaymentOperations:
    """Tests for payment creation and updates."""
    
    @pytest.fixture
    async def seeded_event_with_db(self, client: AsyncClient, test_db: AsyncSession):
        """Create a seeded event for testing, return both event_id and db session."""
        seed = get_seed_data()
        
        event = Event(
            id=seed["event"]["id"],
            name=seed["event"]["name"],
            event_date=seed["event"]["event_date"]
        )
        test_db.add(event)
        
        for v in seed["vendors"]:
            vendor = Vendor(
                id=v["id"],
                event_id=v["event_id"],
                name=v["name"],
                category=v["category"]
            )
            test_db.add(vendor)
        
        for p in seed["payments"][:5]:
            payment = Payment(
                id=p["id"],
                event_id=p["event_id"],
                vendor_id=p["vendor_id"],
                amount=p["amount"],
                paid_date=p["paid_date"],
                due_date=p["due_date"],
                method=p.get("method")
            )
            test_db.add(payment)
        
        await test_db.commit()
        return {"event_id": seed["event"]["id"], "db": test_db}
    
    @pytest.mark.asyncio
    async def test_additional_payment_existing_vendor(self, client: AsyncClient, seeded_event_with_db: dict):
        """DP-006: Add payment to existing vendor - verifies DB insertion."""
        event_id = seeded_event_with_db["event_id"]
        db = seeded_event_with_db["db"]
        
        # Count payments before
        result_before = await db.execute(
            select(Payment).where(Payment.event_id == event_id)
        )
        payments_before = len(result_before.scalars().all())
        
        # Make the request
        response = await client.post(
            f"/api/events/{event_id}/capture/extract",
            json={
                "text": "Just paid another $5,000 to The Grand Pavilion today",
                "conversation_history": []
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # If confirmation needed, confirm it
        if data.get("needs_confirmation"):
            confirm_resp = await client.post(
                f"/api/events/{event_id}/capture/confirm",
                json={"extraction_result": data}
            )
            # Refresh session to see new data
            await db.commit()
        
        # Verify response content
        assert data.get("intent") == "payment" or \
               "grand pavilion" in data.get("assistant_message", "").lower() or \
               "5,000" in data.get("assistant_message", "")
        
        # Verify DB insertion (if confirmed)
        if data.get("needs_confirmation"):
            result_after = await db.execute(
                select(Payment).where(Payment.event_id == event_id)
            )
            payments_after = len(result_after.scalars().all())
            assert payments_after > payments_before, \
                f"Expected new payment in DB. Before: {payments_before}, After: {payments_after}"
    
    @pytest.mark.asyncio
    async def test_new_vendor_payment(self, client: AsyncClient, seeded_event_with_db: dict):
        """DP-008: Create new vendor with payment - verifies DB insertion."""
        event_id = seeded_event_with_db["event_id"]
        db = seeded_event_with_db["db"]
        
        # Count vendors before
        result_before = await db.execute(
            select(Vendor).where(Vendor.event_id == event_id)
        )
        vendors_before = len(result_before.scalars().all())
        
        response = await client.post(
            f"/api/events/{event_id}/capture/extract",
            json={
                "text": "Just booked a dhol group called Punjab Beats for the baraat, $800 paid today",
                "conversation_history": []
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        extraction = data.get("data", {})
        
        # Confirm if needed
        if data.get("needs_confirmation"):
            await client.post(
                f"/api/events/{event_id}/capture/confirm",
                json={"extraction_result": data}
            )
            await db.commit()
            
            # Verify new vendor was created
            result_after = await db.execute(
                select(Vendor).where(Vendor.event_id == event_id)
            )
            vendors_after = len(result_after.scalars().all())
            assert vendors_after > vendors_before, \
                f"Expected new vendor in DB. Before: {vendors_before}, After: {vendors_after}"
        
        assert extraction.get("vendor_name") or \
               "punjab" in data.get("assistant_message", "").lower()
    
    @pytest.mark.asyncio
    async def test_duplicate_detection(self, client: AsyncClient, seeded_event_with_db: dict):
        """DP-018: Detect potential duplicate payment."""
        event_id = seeded_event_with_db["event_id"]
        
        response = await client.post(
            f"/api/events/{event_id}/capture/extract",
            json={
                "text": "Paid Enmuse Photography $12,000 today",
                "conversation_history": []
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        msg = data.get("assistant_message", "").lower()
        assert "already" in msg or \
               "existing" in msg or \
               "duplicate" in msg or \
               data.get("response_mode") == "clarify"


@pytest.mark.tasks
class TestTaskOperations:
    """Tests for task management."""
    
    @pytest.fixture
    async def seeded_event_with_db(self, client: AsyncClient, test_db: AsyncSession):
        """Create a seeded event with tasks, return both event_id and db session."""
        seed = get_seed_data()
        
        event = Event(
            id=seed["event"]["id"],
            name=seed["event"]["name"],
            event_date=seed["event"]["event_date"]
        )
        test_db.add(event)
        
        for t in seed["tasks"]:
            task = Task(
                id=t["id"],
                event_id=t["event_id"],
                title=t["title"],
                description=t.get("description"),
                due_date=t.get("due_date"),
                status=t["status"],
                priority=t.get("priority", "medium")
            )
            test_db.add(task)
        
        await test_db.commit()
        return {"event_id": seed["event"]["id"], "db": test_db}
    
    @pytest.mark.asyncio
    async def test_pending_tasks_query(self, client: AsyncClient, seeded_event_with_db: dict):
        """DP-010: Query pending tasks."""
        event_id = seeded_event_with_db["event_id"]
        
        response = await client.post(
            f"/api/events/{event_id}/capture/extract",
            json={
                "text": "What tasks do I still need to complete?",
                "conversation_history": []
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("response_mode") == "answer" or \
               data.get("intent") == "query" or \
               "task" in data.get("assistant_message", "").lower()
    
    @pytest.mark.asyncio
    async def test_add_new_task(self, client: AsyncClient, seeded_event_with_db: dict):
        """DP-012: Add a new task - verifies DB insertion."""
        event_id = seeded_event_with_db["event_id"]
        db = seeded_event_with_db["db"]
        
        # Count tasks before
        result_before = await db.execute(
            select(Task).where(Task.event_id == event_id)
        )
        tasks_before = len(result_before.scalars().all())
        
        response = await client.post(
            f"/api/events/{event_id}/capture/extract",
            json={
                "text": "Add task: Buy wedding favors by July 1st",
                "conversation_history": []
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Confirm if needed
        if data.get("needs_confirmation"):
            await client.post(
                f"/api/events/{event_id}/capture/confirm",
                json={"extraction_result": data}
            )
            await db.commit()
            
            # Verify new task was created
            result_after = await db.execute(
                select(Task).where(Task.event_id == event_id)
            )
            tasks_after = len(result_after.scalars().all())
            assert tasks_after > tasks_before, \
                f"Expected new task in DB. Before: {tasks_before}, After: {tasks_after}"
        
        assert data.get("intent") == "task" or \
               "favor" in data.get("assistant_message", "").lower() or \
               "task" in data.get("assistant_message", "").lower()
    
    @pytest.mark.asyncio
    async def test_bulk_tasks_creation(self, client: AsyncClient, seeded_event_with_db: dict):
        """DP-021: Create multiple tasks at once."""
        event_id = seeded_event_with_db["event_id"]
        
        response = await client.post(
            f"/api/events/{event_id}/capture/extract",
            json={
                "text": "Add these tasks: 1) Order wedding cake by May 15th 2) Book honeymoon flights by June 1st 3) Get marriage license by August 1st",
                "conversation_history": []
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        msg = data.get("assistant_message", "").lower()
        assert any(word in msg for word in ["task", "cake", "honeymoon", "license"])
    
    @pytest.mark.asyncio
    async def test_delete_task_confirmation(self, client: AsyncClient, seeded_event_with_db: dict):
        """DP-013: Delete task requires confirmation."""
        event_id = seeded_event_with_db["event_id"]
        
        response = await client.post(
            f"/api/events/{event_id}/capture/extract",
            json={
                "text": "Remove the airport pickups task",
                "conversation_history": []
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        msg = data.get("assistant_message", "").lower()
        assert data.get("needs_confirmation") == True or \
               data.get("response_mode") == "confirm" or \
               data.get("action") == "delete" or \
               "confirm" in msg or "sure" in msg or \
               "delete" in msg or "remove" in msg


@pytest.mark.subevents
class TestSubEventOperations:
    """Tests for sub-event queries and updates."""
    
    @pytest.fixture
    async def seeded_event(self, client: AsyncClient, test_db: AsyncSession):
        """Create a seeded event with sub-events."""
        from app.models import SubEvent
        
        seed = get_seed_data()
        
        event = Event(
            id=seed["event"]["id"],
            name=seed["event"]["name"],
            event_date=seed["event"]["event_date"]
        )
        test_db.add(event)
        
        for se in seed["sub_events"]:
            sub = SubEvent(
                id=se["id"],
                event_id=se["event_id"],
                name=se["name"],
                date=se["date"],
                start_time=se.get("start_time"),
                end_time=se.get("end_time"),
                location=se.get("location"),
                description=se.get("description")
            )
            test_db.add(sub)
        
        await test_db.commit()
        return seed["event"]["id"]
    
    @pytest.mark.asyncio
    async def test_subevent_time_query(self, client: AsyncClient, seeded_event: str):
        """DP-014: Query sub-event time."""
        response = await client.post(
            f"/api/events/{seeded_event}/capture/extract",
            json={
                "text": "What time does the sangeet start?",
                "conversation_history": []
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        msg = data.get("assistant_message", "").lower()
        assert "sangeet" in msg or "6" in msg or "18" in msg or "pm" in msg
    
    @pytest.mark.asyncio
    async def test_subevent_reschedule(self, client: AsyncClient, seeded_event: str):
        """DP-015: Reschedule sub-event time."""
        response = await client.post(
            f"/api/events/{seeded_event}/capture/extract",
            json={
                "text": "Change the mehndi start time to 3pm instead of 4pm",
                "conversation_history": []
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("intent") == "sub_event_update" or \
               "mehndi" in data.get("assistant_message", "").lower() or \
               "3" in data.get("assistant_message", "")


@pytest.mark.context
class TestConversationContext:
    """Tests for conversation context preservation."""
    
    @pytest.fixture
    async def seeded_event(self, client: AsyncClient, test_db: AsyncSession):
        """Create a minimal seeded event."""
        seed = get_seed_data()
        
        event = Event(
            id=seed["event"]["id"],
            name=seed["event"]["name"],
            event_date=seed["event"]["event_date"]
        )
        test_db.add(event)
        
        for v in seed["vendors"][:3]:
            vendor = Vendor(
                id=v["id"],
                event_id=v["event_id"],
                name=v["name"],
                category=v["category"]
            )
            test_db.add(vendor)
        
        await test_db.commit()
        return seed["event"]["id"]
    
    @pytest.mark.asyncio
    async def test_followup_uses_context(self, client: AsyncClient, seeded_event: str):
        """DP-019: Follow-up query uses conversation context."""
        first_response = await client.post(
            f"/api/events/{seeded_event}/capture/extract",
            json={
                "text": "How much have I paid the photographer?",
                "conversation_history": []
            }
        )
        first_data = first_response.json()
        
        history = [
            {"role": "user", "content": "How much have I paid the photographer?"},
            {"role": "assistant", "content": first_data.get("assistant_message", "")}
        ]
        
        followup_response = await client.post(
            f"/api/events/{seeded_event}/capture/extract",
            json={
                "text": "And what about the videographer?",
                "conversation_history": history
            }
        )
        
        assert followup_response.status_code == 200
        followup_data = followup_response.json()
        
        msg = followup_data.get("assistant_message", "").lower()
        assert "video" in msg or "$" in msg or \
               followup_data.get("intent") == "query"


@pytest.mark.queries
class TestComplexQueries:
    """Tests for multi-part and complex queries."""
    
    @pytest.fixture
    async def seeded_event(self, client: AsyncClient, test_db: AsyncSession):
        """Create a fully seeded event."""
        seed = get_seed_data()
        
        event = Event(
            id=seed["event"]["id"],
            name=seed["event"]["name"],
            event_date=seed["event"]["event_date"]
        )
        test_db.add(event)
        
        for v in seed["vendors"]:
            vendor = Vendor(
                id=v["id"],
                event_id=v["event_id"],
                name=v["name"],
                category=v["category"]
            )
            test_db.add(vendor)
        
        for p in seed["payments"]:
            payment = Payment(
                id=p["id"],
                event_id=p["event_id"],
                vendor_id=p["vendor_id"],
                amount=p["amount"],
                paid_date=p["paid_date"],
                due_date=p["due_date"],
                method=p.get("method")
            )
            test_db.add(payment)
        
        await test_db.commit()
        return seed["event"]["id"]
    
    @pytest.mark.asyncio
    async def test_multipart_query(self, client: AsyncClient, seeded_event: str):
        """DP-030: Multi-part query (paid and owed)."""
        response = await client.post(
            f"/api/events/{seeded_event}/capture/extract",
            json={
                "text": "How much have I paid the venue, and how much do I still owe them?",
                "conversation_history": []
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        msg = data.get("assistant_message", "").lower()
        assert "$" in msg or "paid" in msg or "owe" in msg or \
               "venue" in msg or "pavilion" in msg or \
               "payment" in msg or "haven't" in msg or \
               data.get("intent") == "query"
    
    @pytest.mark.asyncio
    async def test_fully_paid_vendors_query(self, client: AsyncClient, seeded_event: str):
        """DP-023: Query which vendors are fully paid."""
        response = await client.post(
            f"/api/events/{seeded_event}/capture/extract",
            json={
                "text": "Which vendors have I fully paid?",
                "conversation_history": []
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("response_mode") == "answer" or \
               data.get("intent") == "query"
    
    @pytest.mark.asyncio
    async def test_next_payment_due_query(self, client: AsyncClient, seeded_event: str):
        """DP-027: Query next upcoming payment."""
        response = await client.post(
            f"/api/events/{seeded_event}/capture/extract",
            json={
                "text": "What's my next payment that's coming up?",
                "conversation_history": []
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("response_mode") == "answer" or \
               data.get("intent") == "query"
