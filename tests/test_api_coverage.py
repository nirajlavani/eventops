"""
API Coverage Tests for EventOps.

Covers the REST API endpoints that don't require LLM calls:
- Task CRUD (create, list, get, update, delete)
- Task status sync with payments (kanban drag-and-drop)
- Task vendor_category / assignee / due_time fields
- Calendar event CRUD + notes update
- Vendor payment summary logic (paid vs due totals)
- Dashboard stats endpoint
"""
import pytest
from datetime import date, time as dt_time
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models import Event, Vendor, Payment
from app.models.task import Task, TaskStatus, TaskPriority
from app.models.calendar_event import CalendarEvent


# =============================================================================
# HELPERS
# =============================================================================

async def _make_event(db: AsyncSession, name: str = "Test Event") -> Event:
    event = Event(name=name, event_date=date(2026, 10, 1))
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event


async def _make_vendor(db: AsyncSession, event_id: str, name: str = "Acme Decor",
                       category: str = "decor") -> Vendor:
    vendor = Vendor(event_id=event_id, name=name, category=category)
    db.add(vendor)
    await db.commit()
    await db.refresh(vendor)
    return vendor


# =============================================================================
# TASK CRUD
# =============================================================================

@pytest.mark.tasks
@pytest.mark.fast
class TestTaskCRUD:
    """Verify task REST endpoints work correctly without LLM."""

    @pytest.mark.asyncio
    async def test_create_task(self, client: AsyncClient, test_db: AsyncSession):
        event = await _make_event(test_db)
        resp = await client.post(
            f"/api/events/{event.id}/tasks",
            json={"title": "Buy flowers", "priority": "high"}
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["title"] == "Buy flowers"
        assert body["priority"] == "high"
        assert body["status"] == "pending"

    @pytest.mark.asyncio
    async def test_list_tasks(self, client: AsyncClient, test_db: AsyncSession):
        event = await _make_event(test_db)
        t1 = Task(event_id=event.id, title="Task A", priority="medium")
        t2 = Task(event_id=event.id, title="Task B", priority="low")
        test_db.add_all([t1, t2])
        await test_db.commit()

        resp = await client.get(f"/api/events/{event.id}/tasks")
        assert resp.status_code == 200
        tasks = resp.json()
        assert len(tasks) == 2
        titles = {t["title"] for t in tasks}
        assert "Task A" in titles and "Task B" in titles

    @pytest.mark.asyncio
    async def test_get_single_task(self, client: AsyncClient, test_db: AsyncSession):
        event = await _make_event(test_db)
        task = Task(event_id=event.id, title="Specific task", priority="medium")
        test_db.add(task)
        await test_db.commit()
        await test_db.refresh(task)

        resp = await client.get(f"/api/events/{event.id}/tasks/{task.id}")
        assert resp.status_code == 200
        assert resp.json()["title"] == "Specific task"

    @pytest.mark.asyncio
    async def test_update_task_title(self, client: AsyncClient, test_db: AsyncSession):
        event = await _make_event(test_db)
        task = Task(event_id=event.id, title="Old title", priority="medium")
        test_db.add(task)
        await test_db.commit()
        await test_db.refresh(task)

        resp = await client.put(
            f"/api/events/{event.id}/tasks/{task.id}",
            json={"title": "New title"}
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "New title"

    @pytest.mark.asyncio
    async def test_update_task_vendor_category(self, client: AsyncClient, test_db: AsyncSession):
        """Updating vendor_category via the API should persist."""
        event = await _make_event(test_db)
        task = Task(event_id=event.id, title="Site visit", priority="medium")
        test_db.add(task)
        await test_db.commit()
        await test_db.refresh(task)

        resp = await client.put(
            f"/api/events/{event.id}/tasks/{task.id}",
            json={"vendor_category": "venue"}
        )
        assert resp.status_code == 200
        assert resp.json()["vendor_category"] == "venue"

    @pytest.mark.asyncio
    async def test_update_task_assignee(self, client: AsyncClient, test_db: AsyncSession):
        """Updating assignee via the API should persist."""
        event = await _make_event(test_db)
        task = Task(event_id=event.id, title="Call vendor", priority="medium")
        test_db.add(task)
        await test_db.commit()
        await test_db.refresh(task)

        resp = await client.put(
            f"/api/events/{event.id}/tasks/{task.id}",
            json={"assignee": "Alice, Bob"}
        )
        assert resp.status_code == 200
        assert resp.json()["assignee"] == "Alice, Bob"

    @pytest.mark.asyncio
    async def test_update_task_due_time(self, client: AsyncClient, test_db: AsyncSession):
        """Setting due_time on a task should persist."""
        event = await _make_event(test_db)
        task = Task(event_id=event.id, title="Morning call", priority="medium",
                    due_date=date(2026, 5, 1))
        test_db.add(task)
        await test_db.commit()
        await test_db.refresh(task)

        resp = await client.put(
            f"/api/events/{event.id}/tasks/{task.id}",
            json={"due_time": "09:30:00"}
        )
        assert resp.status_code == 200
        assert resp.json()["due_time"] == "09:30:00"

    @pytest.mark.asyncio
    async def test_delete_task(self, client: AsyncClient, test_db: AsyncSession):
        event = await _make_event(test_db)
        task = Task(event_id=event.id, title="Deletable", priority="low")
        test_db.add(task)
        await test_db.commit()
        await test_db.refresh(task)

        resp = await client.delete(f"/api/events/{event.id}/tasks/{task.id}")
        assert resp.status_code == 204

        check = await test_db.execute(select(Task).where(Task.id == task.id))
        assert check.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_get_nonexistent_task_returns_404(self, client: AsyncClient, test_db: AsyncSession):
        event = await _make_event(test_db)
        resp = await client.get(f"/api/events/{event.id}/tasks/nonexistent-id")
        assert resp.status_code == 404


# =============================================================================
# TASK-PAYMENT SYNC (Kanban drag-to-Done)
# =============================================================================

@pytest.mark.tasks
@pytest.mark.payments
@pytest.mark.fast
class TestTaskPaymentSync:
    """Moving a payment-reminder task to Done should mark the linked payment as paid."""

    @pytest.fixture
    async def task_with_payment(self, client: AsyncClient, test_db: AsyncSession):
        event = await _make_event(test_db, "Sync Test")
        vendor = await _make_vendor(test_db, event.id, "Bloom Florist", "florist")

        payment = Payment(
            event_id=event.id,
            vendor_id=vendor.id,
            amount=Decimal("5000"),
            paid_date=None,
            due_date=date(2026, 6, 1),
        )
        test_db.add(payment)

        task = Task(
            event_id=event.id,
            vendor_id=vendor.id,
            vendor_category="florist",
            title="Payment due: $5,000 to Bloom Florist",
            due_date=date(2026, 6, 1),
            status=TaskStatus.PENDING,
            priority=TaskPriority.HIGH,
        )
        test_db.add(task)
        await test_db.commit()
        await test_db.refresh(payment)
        await test_db.refresh(task)

        return {"event_id": event.id, "task_id": task.id, "payment_id": payment.id}

    @pytest.mark.asyncio
    async def test_completing_task_marks_payment_paid(
        self, client: AsyncClient, test_db: AsyncSession, task_with_payment: dict
    ):
        eid = task_with_payment["event_id"]
        tid = task_with_payment["task_id"]
        pid = task_with_payment["payment_id"]

        resp = await client.put(
            f"/api/events/{eid}/tasks/{tid}",
            json={"status": "completed"}
        )
        assert resp.status_code == 200

        result = await test_db.execute(select(Payment).where(Payment.id == pid))
        payment = result.scalar_one()
        assert payment.paid_date is not None, "Payment should be marked paid after task completion"

    @pytest.mark.asyncio
    async def test_undoing_task_reverses_payment(
        self, client: AsyncClient, test_db: AsyncSession, task_with_payment: dict
    ):
        eid = task_with_payment["event_id"]
        tid = task_with_payment["task_id"]
        pid = task_with_payment["payment_id"]

        await client.put(f"/api/events/{eid}/tasks/{tid}", json={"status": "completed"})
        await client.put(f"/api/events/{eid}/tasks/{tid}", json={"status": "pending"})

        result = await test_db.execute(select(Payment).where(Payment.id == pid))
        payment = result.scalar_one()
        assert payment.paid_date is None, "Payment should revert to unpaid when task is un-completed"


# =============================================================================
# CALENDAR EVENT CRUD + NOTES
# =============================================================================

@pytest.mark.fast
class TestCalendarEventCRUD:
    """Verify calendar event endpoints and notes editing."""

    @pytest.mark.asyncio
    async def test_create_calendar_event(self, client: AsyncClient, test_db: AsyncSession):
        event = await _make_event(test_db)
        resp = await client.post(
            f"/api/events/{event.id}/calendar",
            json={"title": "Venue Tour", "event_date": "2026-05-13", "event_time": "12:00:00",
                  "location": "Trenton, GA", "notes": "Hall walkthrough"}
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["title"] == "Venue Tour"
        assert body["event_time"] == "12:00:00"
        assert body["notes"] == "Hall walkthrough"

    @pytest.mark.asyncio
    async def test_list_calendar_events(self, client: AsyncClient, test_db: AsyncSession):
        event = await _make_event(test_db)
        ce = CalendarEvent(event_id=event.id, title="Meeting", event_date=date(2026, 5, 1))
        test_db.add(ce)
        await test_db.commit()

        resp = await client.get(f"/api/events/{event.id}/calendar")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    @pytest.mark.asyncio
    async def test_update_calendar_event_notes(self, client: AsyncClient, test_db: AsyncSession):
        """Editing notes on a calendar event should persist."""
        event = await _make_event(test_db)
        ce = CalendarEvent(event_id=event.id, title="Tour", event_date=date(2026, 5, 13),
                           notes="Original")
        test_db.add(ce)
        await test_db.commit()
        await test_db.refresh(ce)

        resp = await client.put(
            f"/api/events/{event.id}/calendar/{ce.id}",
            json={"notes": "Updated notes with <b>formatting</b>"}
        )
        assert resp.status_code == 200
        assert "Updated notes" in resp.json()["notes"]

    @pytest.mark.asyncio
    async def test_update_calendar_event_title(self, client: AsyncClient, test_db: AsyncSession):
        event = await _make_event(test_db)
        ce = CalendarEvent(event_id=event.id, title="Old Title", event_date=date(2026, 6, 1))
        test_db.add(ce)
        await test_db.commit()
        await test_db.refresh(ce)

        resp = await client.put(
            f"/api/events/{event.id}/calendar/{ce.id}",
            json={"title": "New Title"}
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "New Title"

    @pytest.mark.asyncio
    async def test_delete_calendar_event(self, client: AsyncClient, test_db: AsyncSession):
        event = await _make_event(test_db)
        ce = CalendarEvent(event_id=event.id, title="Deletable", event_date=date(2026, 7, 1))
        test_db.add(ce)
        await test_db.commit()
        await test_db.refresh(ce)

        resp = await client.delete(f"/api/events/{event.id}/calendar/{ce.id}")
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_get_nonexistent_calendar_event_returns_404(self, client: AsyncClient, test_db: AsyncSession):
        event = await _make_event(test_db)
        resp = await client.get(f"/api/events/{event.id}/calendar/nonexistent-id")
        assert resp.status_code == 404


# =============================================================================
# VENDOR PAYMENT TOTALS
# =============================================================================

@pytest.mark.payments
@pytest.mark.fast
class TestVendorPaymentTotals:
    """Verify vendor payment API returns data that lets frontend compute correct totals."""

    @pytest.fixture
    async def vendor_with_payments(self, client: AsyncClient, test_db: AsyncSession):
        event = await _make_event(test_db, "Payment Totals Test")
        vendor = await _make_vendor(test_db, event.id, "Grand Venue", "venue")

        p_paid = Payment(
            event_id=event.id, vendor_id=vendor.id,
            amount=Decimal("16000"), paid_date=date(2026, 1, 15),
        )
        p_due1 = Payment(
            event_id=event.id, vendor_id=vendor.id,
            amount=Decimal("16000"), due_date=date(2026, 5, 1),
        )
        p_due2 = Payment(
            event_id=event.id, vendor_id=vendor.id,
            amount=Decimal("16000"), due_date=date(2026, 11, 28),
        )
        test_db.add_all([p_paid, p_due1, p_due2])
        await test_db.commit()

        return {"event_id": event.id, "vendor_id": vendor.id}

    @pytest.mark.asyncio
    async def test_payments_endpoint_returns_correct_amounts(
        self, client: AsyncClient, test_db: AsyncSession, vendor_with_payments: dict
    ):
        eid = vendor_with_payments["event_id"]
        vid = vendor_with_payments["vendor_id"]

        resp = await client.get(f"/api/events/{eid}/payments")
        assert resp.status_code == 200
        payments = resp.json()

        vendor_payments = [p for p in payments if p.get("vendor_id") == vid]
        assert len(vendor_payments) == 3

        paid = [p for p in vendor_payments if p.get("paid_date")]
        pending = [p for p in vendor_payments if not p.get("paid_date")]

        total_paid = sum(float(p.get("amount", 0) or p.get("amount_paid", 0)) for p in paid)
        total_due = sum(float(p.get("amount", 0) or p.get("amount_paid", 0)) for p in pending)

        assert total_paid == 16000.0, f"Expected $16,000 paid, got ${total_paid}"
        assert total_due == 32000.0, f"Expected $32,000 due, got ${total_due}"


# =============================================================================
# TASK VENDOR_CATEGORY RESOLUTION IN LIST
# =============================================================================

@pytest.mark.tasks
@pytest.mark.fast
class TestTaskVendorResolution:
    """Verify task list endpoint resolves vendor_name and vendor_category."""

    @pytest.mark.asyncio
    async def test_task_returns_vendor_name_when_linked(
        self, client: AsyncClient, test_db: AsyncSession
    ):
        event = await _make_event(test_db)
        vendor = await _make_vendor(test_db, event.id, "Bloom Decor", "decor")
        task = Task(
            event_id=event.id, vendor_id=vendor.id, vendor_category="decor",
            title="Pay Bloom Decor", priority="high",
        )
        test_db.add(task)
        await test_db.commit()
        await test_db.refresh(task)

        resp = await client.get(f"/api/events/{event.id}/tasks")
        assert resp.status_code == 200
        tasks = resp.json()
        assert len(tasks) == 1
        assert tasks[0]["vendor_name"] == "Bloom Decor"
        assert tasks[0]["vendor_category"] == "decor"

    @pytest.mark.asyncio
    async def test_task_without_vendor_has_null_vendor_name(
        self, client: AsyncClient, test_db: AsyncSession
    ):
        event = await _make_event(test_db)
        task = Task(event_id=event.id, title="Generic todo", priority="medium")
        test_db.add(task)
        await test_db.commit()

        resp = await client.get(f"/api/events/{event.id}/tasks")
        tasks = resp.json()
        assert tasks[0]["vendor_name"] is None
        assert tasks[0]["vendor_category"] is None


# =============================================================================
# EXTRACTION SERVICE — TASK UPDATE/DELETE
# =============================================================================

@pytest.mark.tasks
@pytest.mark.fast
class TestExtractionTaskOps:
    """Verify the extraction service can update and delete tasks by ID."""

    @pytest.mark.asyncio
    async def test_update_task_by_id_changes_vendor_category(
        self, client: AsyncClient, test_db: AsyncSession
    ):
        from app.services.extraction import ExtractionService

        event = await _make_event(test_db)
        task = Task(event_id=event.id, title="Venue Site Visit", priority="medium")
        test_db.add(task)
        await test_db.commit()
        await test_db.refresh(task)

        svc = ExtractionService()
        updated_id = await svc._update_task_by_id(
            task.id, {"vendor_category": "venue"}, test_db
        )
        assert updated_id == task.id

        result = await test_db.execute(select(Task).where(Task.id == task.id))
        refreshed = result.scalar_one()
        assert refreshed.vendor_category == "venue"

    @pytest.mark.asyncio
    async def test_update_task_by_id_changes_priority(
        self, client: AsyncClient, test_db: AsyncSession
    ):
        from app.services.extraction import ExtractionService

        event = await _make_event(test_db)
        task = Task(event_id=event.id, title="Some Task", priority="low")
        test_db.add(task)
        await test_db.commit()
        await test_db.refresh(task)

        svc = ExtractionService()
        await svc._update_task_by_id(task.id, {"priority": "high"}, test_db)

        result = await test_db.execute(select(Task).where(Task.id == task.id))
        refreshed = result.scalar_one()
        assert refreshed.priority == TaskPriority.HIGH

    @pytest.mark.asyncio
    async def test_delete_record_removes_task(
        self, client: AsyncClient, test_db: AsyncSession
    ):
        from app.services.extraction import ExtractionService
        from app.schemas.capture import IntentType

        event = await _make_event(test_db)
        task = Task(event_id=event.id, title="To Delete", priority="low")
        test_db.add(task)
        await test_db.commit()
        await test_db.refresh(task)

        svc = ExtractionService()
        deleted_id = await svc._delete_record(IntentType.TASK, task.id, test_db)
        assert deleted_id == task.id

        result = await test_db.execute(select(Task).where(Task.id == task.id))
        assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_create_task_with_vendor_category(
        self, client: AsyncClient, test_db: AsyncSession
    ):
        from app.services.extraction import ExtractionService

        event = await _make_event(test_db)
        svc = ExtractionService()
        task_id = await svc._create_task(
            event.id,
            {"title": "Venue Visit", "vendor_category": "venue", "priority": "high"},
            test_db,
        )

        result = await test_db.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one()
        assert task.vendor_category == "venue"
        assert task.title == "Venue Visit"


# =============================================================================
# CONTEXT SERVICE — TASK ID + CATEGORY IN PROMPT
# =============================================================================

@pytest.mark.fast
class TestContextService:
    """Verify context service includes task IDs and vendor_category for LLM."""

    @pytest.mark.asyncio
    async def test_context_includes_task_ids(
        self, client: AsyncClient, test_db: AsyncSession
    ):
        from app.services.context_service import ContextService

        event = await _make_event(test_db)
        task = Task(
            event_id=event.id, title="Pay Florist", priority="high",
            vendor_category="florist",
        )
        test_db.add(task)
        await test_db.commit()
        await test_db.refresh(task)

        svc = ContextService()
        ctx = await svc.get_full_context(event.id, test_db)
        formatted = svc.format_full_context_for_prompt(ctx)

        assert f"TASK_ID={task.id}" in formatted
        assert "Pay Florist" in formatted
        assert "[label: florist]" in formatted

    @pytest.mark.asyncio
    async def test_context_shows_completed_tasks(
        self, client: AsyncClient, test_db: AsyncSession
    ):
        from app.services.context_service import ContextService

        event = await _make_event(test_db)
        task = Task(
            event_id=event.id, title="Done Task", priority="medium",
            status=TaskStatus.COMPLETED,
        )
        test_db.add(task)
        await test_db.commit()
        await test_db.refresh(task)

        svc = ContextService()
        ctx = await svc.get_full_context(event.id, test_db)
        formatted = svc.format_full_context_for_prompt(ctx)

        assert "COMPLETED TASKS" in formatted
        assert "Done Task" in formatted


# =============================================================================
# DASHBOARD ENDPOINT
# =============================================================================

@pytest.mark.dashboard
@pytest.mark.fast
class TestDashboard:
    """Verify dashboard stats endpoint returns expected structure."""

    @pytest.mark.asyncio
    async def test_dashboard_returns_financial_summary(
        self, client: AsyncClient, test_db: AsyncSession
    ):
        event = await _make_event(test_db)
        vendor = await _make_vendor(test_db, event.id, "Test Vendor", "venue")

        p = Payment(event_id=event.id, vendor_id=vendor.id,
                    amount=Decimal("10000"), paid_date=date(2026, 1, 1))
        test_db.add(p)
        await test_db.commit()

        resp = await client.get(f"/api/events/{event.id}/dashboard")
        assert resp.status_code == 200
        body = resp.json()
        assert "financial_summary" in body or "paid_to_vendors" in body


# =============================================================================
# VENDOR DEDUPLICATION
# =============================================================================

@pytest.mark.extraction
@pytest.mark.fast
class TestVendorDeduplication:
    """Verify that vendor creation never produces duplicates."""

    @pytest.mark.asyncio
    async def test_create_vendor_deduplicates(self, test_db: AsyncSession):
        from app.services.extraction import ExtractionService

        event = await _make_event(test_db)
        svc = ExtractionService()

        vid1 = await svc._create_vendor(event.id, {"name": "Blackberry Ridge", "category": "venue", "notes": "Location: Trenton, GA"}, test_db)
        vid2 = await svc._create_vendor(event.id, {"name": "Blackberry Ridge", "category": "venue", "notes": "Capacity: 200"}, test_db)

        assert vid1 == vid2

        vendors = (await test_db.execute(select(Vendor).where(Vendor.event_id == event.id))).scalars().all()
        assert len(vendors) == 1
        assert "Trenton" in vendors[0].notes
        assert "Capacity" in vendors[0].notes

    @pytest.mark.asyncio
    async def test_payment_then_secondary_no_dup(self, test_db: AsyncSession):
        from app.services.extraction import ExtractionService

        event = await _make_event(test_db)
        svc = ExtractionService()

        await svc._create_payment(event.id, {
            "vendor_name": "Blackberry Ridge",
            "vendor_category": "venue",
            "amount_paid": 16000,
            "payment_date": "2025-09-07",
        }, test_db)

        await svc._create_vendor(event.id, {"name": "Blackberry Ridge", "category": "venue", "notes": "Location: Trenton"}, test_db)

        vendors = (await test_db.execute(select(Vendor).where(Vendor.event_id == event.id))).scalars().all()
        assert len(vendors) == 1

    @pytest.mark.asyncio
    async def test_resolve_or_create_creates_when_missing(self, test_db: AsyncSession):
        from app.services.extraction import ExtractionService

        event = await _make_event(test_db)
        svc = ExtractionService()

        vid = await svc._resolve_or_create_vendor(event.id, "New Vendor", "photography", None, test_db)
        assert vid is not None

        vendors = (await test_db.execute(select(Vendor).where(Vendor.event_id == event.id))).scalars().all()
        assert len(vendors) == 1
        assert vendors[0].name == "New Vendor"


# =============================================================================
# VENDOR CASCADE DELETE
# =============================================================================

@pytest.mark.extraction
@pytest.mark.fast
class TestVendorCascadeDelete:
    """Verify vendor delete removes associated payments and tasks."""

    @pytest.mark.asyncio
    async def test_delete_vendor_cascades(self, test_db: AsyncSession):
        from app.services.extraction import ExtractionService

        event = await _make_event(test_db)
        vendor = await _make_vendor(test_db, event.id, "Soon Gone DJ", "music_dj")

        p = Payment(event_id=event.id, vendor_id=vendor.id, amount=Decimal("5000"), paid_date=date(2026, 1, 1))
        test_db.add(p)
        t = Task(event_id=event.id, vendor_id=vendor.id, title="Pay DJ", priority="high", status=TaskStatus.PENDING)
        test_db.add(t)
        await test_db.commit()

        svc = ExtractionService()
        deleted = await svc._delete_vendor_cascade(event.id, vendor.id, test_db)
        assert deleted is True

        v_count = (await test_db.execute(select(func.count()).select_from(Vendor).where(Vendor.event_id == event.id))).scalar()
        p_count = (await test_db.execute(select(func.count()).select_from(Payment).where(Payment.event_id == event.id))).scalar()
        t_count = (await test_db.execute(select(func.count()).select_from(Task).where(Task.event_id == event.id))).scalar()

        assert v_count == 0
        assert p_count == 0
        assert t_count == 0


# =============================================================================
# PAYMENT UPDATE MATCHING
# =============================================================================

@pytest.mark.extraction
@pytest.mark.fast
class TestPaymentUpdateMatching:
    """Verify _find_and_update_payment matches and updates existing payments."""

    @pytest.mark.asyncio
    async def test_find_and_update_adds_method(self, test_db: AsyncSession):
        from app.services.extraction import ExtractionService

        event = await _make_event(test_db)
        vendor = await _make_vendor(test_db, event.id, "Blackberry Ridge", "venue")

        p = Payment(event_id=event.id, vendor_id=vendor.id, amount=Decimal("16000"), paid_date=date(2025, 9, 7))
        test_db.add(p)
        await test_db.commit()
        await test_db.refresh(p)

        svc = ExtractionService()
        matched = await svc._find_and_update_payment(event.id, {
            "vendor_name": "Blackberry Ridge",
            "amount_paid": 16000,
            "method": "credit_card",
            "notes": "Capital One Venture X",
        }, test_db)

        assert matched is True

        updated = (await test_db.execute(select(Payment).where(Payment.id == p.id))).scalar_one()
        assert updated.method == "credit_card"
        assert "Capital One" in updated.notes

    @pytest.mark.asyncio
    async def test_find_and_update_no_match_returns_false(self, test_db: AsyncSession):
        from app.services.extraction import ExtractionService

        event = await _make_event(test_db)
        svc = ExtractionService()

        matched = await svc._find_and_update_payment(event.id, {
            "vendor_name": "NonExistent",
            "amount_paid": 99999,
        }, test_db)
        assert matched is False


# =============================================================================
# CONTEXT SERVICE — VENDOR & PAYMENT ENRICHMENT
# =============================================================================

@pytest.mark.context
@pytest.mark.fast
class TestContextEnrichment:
    """Verify context_service provides vendor IDs, payment IDs, methods, and notes."""

    @pytest.mark.asyncio
    async def test_context_includes_vendor_ids_and_notes(self, test_db: AsyncSession):
        from app.services.context_service import ContextService

        event = await _make_event(test_db)
        vendor = Vendor(event_id=event.id, name="Lush Florals", category="florist", notes="Downtown location", contact_info="Jane 555-1234")
        test_db.add(vendor)
        await test_db.commit()
        await test_db.refresh(vendor)

        svc = ContextService()
        ctx = await svc.get_full_context(event.id, test_db)
        formatted = svc.format_full_context_for_prompt(ctx)

        assert f"VENDOR_ID={vendor.id}" in formatted
        assert "Lush Florals" in formatted
        assert "Downtown location" in formatted
        assert "Jane 555-1234" in formatted

    @pytest.mark.asyncio
    async def test_context_includes_payment_ids_and_methods(self, test_db: AsyncSession):
        from app.services.context_service import ContextService

        event = await _make_event(test_db)
        vendor = await _make_vendor(test_db, event.id, "Quick Photo", "photography")

        p = Payment(event_id=event.id, vendor_id=vendor.id, amount=Decimal("3000"), paid_date=date(2026, 2, 1), method="credit_card")
        test_db.add(p)
        await test_db.commit()
        await test_db.refresh(p)

        svc = ContextService()
        ctx = await svc.get_full_context(event.id, test_db)
        formatted = svc.format_full_context_for_prompt(ctx)

        assert f"PAYMENT_ID={p.id}" in formatted
        assert "credit_card" in formatted
        assert "Quick Photo" in formatted

    @pytest.mark.asyncio
    async def test_vendors_listed_before_payments(self, test_db: AsyncSession):
        from app.services.context_service import ContextService

        event = await _make_event(test_db)
        vendor = await _make_vendor(test_db, event.id, "Vendor First", "venue")
        p = Payment(event_id=event.id, vendor_id=vendor.id, amount=Decimal("1000"), paid_date=date(2026, 1, 1))
        test_db.add(p)
        await test_db.commit()

        svc = ContextService()
        ctx = await svc.get_full_context(event.id, test_db)
        formatted = svc.format_full_context_for_prompt(ctx)

        vendor_pos = formatted.find("BOOKED VENDORS")
        payment_pos = formatted.find("COMPLETED PAYMENTS")
        assert vendor_pos < payment_pos


# =============================================================================
# DUPLICATE PAYMENT & TASK GUARDS
# =============================================================================

@pytest.mark.extraction
@pytest.mark.fast
class TestDuplicateGuards:
    """Verify that duplicate payments and tasks are never created."""

    @pytest.mark.asyncio
    async def test_no_duplicate_pending_payment(self, test_db: AsyncSession):
        """Calling _create_payment twice with same remaining_balance should NOT create two pending records."""
        from app.services.extraction import ExtractionService

        event = await _make_event(test_db)
        svc = ExtractionService()

        await svc._create_payment(event.id, {
            "vendor_name": "Ridge Venue",
            "vendor_category": "venue",
            "amount_paid": 16000,
            "payment_date": "2025-09-07",
            "remaining_balance": 20000,
            "due_date": "2026-05-01",
        }, test_db)

        await svc._create_payment(event.id, {
            "vendor_name": "Ridge Venue",
            "vendor_category": "venue",
            "amount_paid": 10000,
            "payment_date": "2026-01-01",
            "remaining_balance": 20000,
            "due_date": "2026-05-01",
        }, test_db)

        all_payments = (await test_db.execute(select(Payment).where(Payment.event_id == event.id))).scalars().all()
        pending = [p for p in all_payments if p.paid_date is None]
        paid = [p for p in all_payments if p.paid_date is not None]

        assert len(pending) == 1, f"Expected 1 pending payment, got {len(pending)}"
        assert len(paid) == 2, f"Expected 2 paid payments, got {len(paid)}"
        assert float(pending[0].amount) == 20000

    @pytest.mark.asyncio
    async def test_no_duplicate_reminder_task(self, test_db: AsyncSession):
        """Creating two payments with same remaining_balance should NOT create two reminder tasks."""
        from app.services.extraction import ExtractionService

        event = await _make_event(test_db)
        svc = ExtractionService()

        await svc._create_payment(event.id, {
            "vendor_name": "DJ Beats",
            "vendor_category": "music_dj",
            "amount_paid": 5000,
            "payment_date": "2025-12-01",
            "remaining_balance": 10000,
            "due_date": "2026-06-01",
        }, test_db)

        await svc._create_payment(event.id, {
            "vendor_name": "DJ Beats",
            "vendor_category": "music_dj",
            "amount_paid": 3000,
            "payment_date": "2026-02-01",
            "remaining_balance": 10000,
            "due_date": "2026-06-01",
        }, test_db)

        tasks = (await test_db.execute(select(Task).where(Task.event_id == event.id))).scalars().all()
        assert len(tasks) == 1, f"Expected 1 task, got {len(tasks)}: {[t.title for t in tasks]}"

    @pytest.mark.asyncio
    async def test_no_zero_dollar_payment(self, test_db: AsyncSession):
        """A payment with $0 amount and no remaining should not be created."""
        from app.services.extraction import ExtractionService

        event = await _make_event(test_db)
        svc = ExtractionService()

        result_id = await svc._create_payment(event.id, {
            "vendor_name": "Zero Corp",
            "vendor_category": "other",
            "amount_paid": 0,
        }, test_db)

        assert result_id == ""
        all_payments = (await test_db.execute(select(Payment).where(Payment.event_id == event.id))).scalars().all()
        assert len(all_payments) == 0

    @pytest.mark.asyncio
    async def test_duplicate_paid_payment_updates_instead(self, test_db: AsyncSession):
        """Creating a paid payment that already exists should update method, not create duplicate."""
        from app.services.extraction import ExtractionService

        event = await _make_event(test_db)
        svc = ExtractionService()

        pid1 = await svc._create_payment(event.id, {
            "vendor_name": "Bloom Florist",
            "vendor_category": "florist",
            "amount_paid": 8000,
            "payment_date": "2026-03-01",
        }, test_db)

        pid2 = await svc._create_payment(event.id, {
            "vendor_name": "Bloom Florist",
            "vendor_category": "florist",
            "amount_paid": 8000,
            "payment_date": "2026-03-01",
            "method": "credit_card",
        }, test_db)

        assert pid1 == pid2

        all_payments = (await test_db.execute(select(Payment).where(Payment.event_id == event.id))).scalars().all()
        assert len(all_payments) == 1
        assert all_payments[0].method == "credit_card"


class TestMultiplePaymentItems:
    """Test the items-based bulk payment creation flow (the fix for the Blackberry Ridge bug)."""

    @pytest.mark.asyncio
    async def test_items_creates_correct_payments(self, test_db: AsyncSession):
        """3 items (2 paid, 1 pending) should create exactly 3 payments with correct dates."""
        from app.services.extraction import ExtractionService

        event = await _make_event(test_db)
        svc = ExtractionService()

        items = [
            {"vendor_name": "Blackberry Ridge", "vendor_category": "venue", "amount_paid": 16000, "payment_date": "2025-09-07", "vendor_notes": "Location: Trenton, GA"},
            {"vendor_name": "Blackberry Ridge", "vendor_category": "venue", "amount_paid": 10000, "payment_date": "2026-01-01"},
            {"vendor_name": "Blackberry Ridge", "vendor_category": "venue", "amount_paid": 20000, "due_date": "2026-05-01"},
        ]

        created_ids = []
        for item in items:
            pid = await svc._create_payment(event.id, item, test_db)
            created_ids.append(pid)

        payments = (await test_db.execute(
            select(Payment).where(Payment.event_id == event.id).order_by(Payment.created_at)
        )).scalars().all()

        assert len(payments) == 3, f"Expected 3, got {len(payments)}"
        zero = [p for p in payments if float(p.amount) == 0]
        assert len(zero) == 0, f"Found $0 payments: {zero}"

        paid = [p for p in payments if p.paid_date]
        pending = [p for p in payments if not p.paid_date]
        assert len(paid) == 2
        assert len(pending) == 1
        assert float(pending[0].amount) == 20000
        assert str(pending[0].due_date) == "2026-05-01"

    @pytest.mark.asyncio
    async def test_items_creates_single_vendor(self, test_db: AsyncSession):
        """Multiple items for the same vendor should not create duplicate vendors."""
        from app.services.extraction import ExtractionService

        event = await _make_event(test_db)
        svc = ExtractionService()

        for item in [
            {"vendor_name": "Blackberry Ridge", "vendor_category": "venue", "amount_paid": 16000, "payment_date": "2025-09-07"},
            {"vendor_name": "Blackberry Ridge", "vendor_category": "venue", "amount_paid": 10000, "payment_date": "2026-01-01"},
            {"vendor_name": "Blackberry Ridge", "vendor_category": "venue", "amount_paid": 20000, "due_date": "2026-05-01"},
        ]:
            await svc._create_payment(event.id, item, test_db)

        vendors = (await test_db.execute(select(Vendor).where(Vendor.event_id == event.id))).scalars().all()
        assert len(vendors) == 1, f"Expected 1 vendor, got {len(vendors)}"
        assert vendors[0].name == "Blackberry Ridge"

    @pytest.mark.asyncio
    async def test_items_creates_single_task(self, test_db: AsyncSession):
        """Only the pending payment item should create a task, and only one."""
        from app.services.extraction import ExtractionService

        event = await _make_event(test_db)
        svc = ExtractionService()

        for item in [
            {"vendor_name": "Blackberry Ridge", "vendor_category": "venue", "amount_paid": 16000, "payment_date": "2025-09-07"},
            {"vendor_name": "Blackberry Ridge", "vendor_category": "venue", "amount_paid": 10000, "payment_date": "2026-01-01"},
            {"vendor_name": "Blackberry Ridge", "vendor_category": "venue", "amount_paid": 20000, "due_date": "2026-05-01"},
        ]:
            await svc._create_payment(event.id, item, test_db)

        tasks = (await test_db.execute(select(Task).where(Task.event_id == event.id))).scalars().all()
        assert len(tasks) == 1, f"Expected 1 task, got {len(tasks)}: {[t.title for t in tasks]}"
        assert "20,000" in tasks[0].title or "20000" in tasks[0].title

    @pytest.mark.asyncio
    async def test_update_items_adds_methods_without_duplicates(self, test_db: AsyncSession):
        """Updating payment items with methods should not create new payments."""
        from app.services.extraction import ExtractionService

        event = await _make_event(test_db)
        svc = ExtractionService()

        for item in [
            {"vendor_name": "Blackberry Ridge", "vendor_category": "venue", "amount_paid": 16000, "payment_date": "2025-09-07"},
            {"vendor_name": "Blackberry Ridge", "vendor_category": "venue", "amount_paid": 10000, "payment_date": "2026-01-01"},
            {"vendor_name": "Blackberry Ridge", "vendor_category": "venue", "amount_paid": 20000, "due_date": "2026-05-01"},
        ]:
            await svc._create_payment(event.id, item, test_db)

        update_items = [
            {"vendor_name": "Blackberry Ridge", "amount_paid": 16000, "payment_date": "2025-09-07", "method": "credit_card"},
            {"vendor_name": "Blackberry Ridge", "amount_paid": 10000, "payment_date": "2026-01-01", "method": "bank_ach"},
        ]
        for item in update_items:
            await svc._find_and_update_payment(event.id, item, test_db)

        payments = (await test_db.execute(
            select(Payment).where(Payment.event_id == event.id).order_by(Payment.created_at)
        )).scalars().all()
        assert len(payments) == 3, f"Expected 3 after update, got {len(payments)}"

        paid = [p for p in payments if p.paid_date]
        methods = {p.method for p in paid}
        assert "credit_card" in methods
        assert "bank_ach" in methods
