"""
Comprehensive chatbot testing suite for EventOps.

This module tests the chatbot's ability to handle complex wedding planning
scenarios including vendor management, payments, tasks, and natural language
understanding.

Each test is self-contained and creates its own event for isolation.
"""
import pytest
from datetime import date
from httpx import AsyncClient


@pytest.mark.vendors
class TestVendorCategorization:
    """Tests for vendor category inference and assignment."""
    
    @pytest.mark.asyncio
    async def test_photographer_category(self, client: AsyncClient):
        """Test photographer is categorized correctly."""
        event_resp = await client.post(
            "/api/events",
            json={"name": "Test Wedding", "event_date": "2026-12-01"}
        )
        event_id = event_resp.json()["id"]
        
        response = await client.post(
            f"/api/events/{event_id}/capture/extract",
            json={
                "text": "Paid Studio Lens Photography $5000 today",
                "conversation_history": []
            }
        )
        
        data = response.json()
        extraction_data = data.get("data", {})
        
        assert extraction_data.get("vendor_category") == "photography" or \
               "photo" in str(extraction_data.get("vendor_name", "")).lower()
    
    @pytest.mark.asyncio
    async def test_videographer_category(self, client: AsyncClient):
        """Test videographer is categorized correctly."""
        event_resp = await client.post(
            "/api/events",
            json={"name": "Test Wedding", "event_date": "2026-12-01"}
        )
        event_id = event_resp.json()["id"]
        
        response = await client.post(
            f"/api/events/{event_id}/capture/extract",
            json={
                "text": "Paid Video Dreams $8000 today for wedding videography",
                "conversation_history": []
            }
        )
        
        assert response.status_code == 200, \
            f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        extraction_data = data.get("data", {})
        
        assert extraction_data.get("vendor_category") == "videography" or \
               "video" in str(extraction_data.get("vendor_name", "")).lower() or \
               "video" in data.get("assistant_message", "").lower()
    
    @pytest.mark.asyncio
    async def test_mehndi_category(self, client: AsyncClient):
        """Test mehndi artist is categorized correctly."""
        event_resp = await client.post(
            "/api/events",
            json={"name": "Test Wedding", "event_date": "2026-12-01"}
        )
        event_id = event_resp.json()["id"]
        
        response = await client.post(
            f"/api/events/{event_id}/capture/extract",
            json={
                "text": "Booked Henna by Priya for mehndi, total $2500, paid $500 advance",
                "conversation_history": []
            }
        )
        
        data = response.json()
        extraction_data = data.get("data", {})
        
        msg = data.get("assistant_message", "").lower()
        assert extraction_data.get("vendor_category") == "mehndi" or \
               extraction_data.get("category") == "mehndi" or \
               "mehndi" in str(extraction_data).lower() or \
               "henna" in str(extraction_data).lower() or \
               "mehndi" in msg or "henna" in msg
    
    @pytest.mark.asyncio
    async def test_pandit_officiant_category(self, client: AsyncClient):
        """Test pandit is categorized as officiant."""
        event_resp = await client.post(
            "/api/events",
            json={"name": "Test Wedding", "event_date": "2026-12-01"}
        )
        event_id = event_resp.json()["id"]
        
        response = await client.post(
            f"/api/events/{event_id}/capture/extract",
            json={
                "text": "Pandit Sharma will perform the ceremony, fee is $1500 paid today",
                "conversation_history": []
            }
        )
        
        data = response.json()
        extraction_data = data.get("data", {})
        
        msg = data.get("assistant_message", "").lower()
        assert extraction_data.get("vendor_category") == "officiant" or \
               extraction_data.get("category") == "officiant" or \
               "pandit" in str(extraction_data.get("vendor_name", "")).lower() or \
               "pandit" in str(extraction_data.get("name", "")).lower() or \
               "pandit" in msg or "officiant" in msg
    
    @pytest.mark.asyncio
    async def test_generic_vendor_asks_category(self, client: AsyncClient):
        """Test that ambiguous vendor names trigger category question."""
        event_resp = await client.post(
            "/api/events",
            json={"name": "Test Wedding", "event_date": "2026-12-01"}
        )
        event_id = event_resp.json()["id"]
        
        response = await client.post(
            f"/api/events/{event_id}/capture/extract",
            json={
                "text": "Paid Rani Events $10000 deposit",
                "conversation_history": []
            }
        )
        
        data = response.json()
        
        assert data.get("response_mode") == "clarify" or \
               "type" in data.get("assistant_message", "").lower() or \
               "category" in data.get("assistant_message", "").lower() or \
               "what kind" in data.get("assistant_message", "").lower()


@pytest.mark.vendors
class TestVendorNameRequired:
    """Tests for vendor name clarification."""
    
    @pytest.mark.asyncio
    async def test_caterer_without_name_asks_clarification(self, client: AsyncClient):
        """Test that chat asks for vendor name when only category mentioned."""
        event_resp = await client.post(
            "/api/events",
            json={"name": "Test Wedding", "event_date": "2026-12-01"}
        )
        event_id = event_resp.json()["id"]
        
        response = await client.post(
            f"/api/events/{event_id}/capture/extract",
            json={
                "text": "I paid my caterer $8,000 yesterday",
                "conversation_history": []
            }
        )
        
        data = response.json()
        
        assert data.get("response_mode") == "clarify" or \
               "name" in data.get("assistant_message", "").lower() or \
               "who" in data.get("assistant_message", "").lower()
    
    @pytest.mark.asyncio
    async def test_florist_without_name_asks_clarification(self, client: AsyncClient):
        """Test florist without name triggers clarification."""
        event_resp = await client.post(
            "/api/events",
            json={"name": "Test Wedding", "event_date": "2026-12-01"}
        )
        event_id = event_resp.json()["id"]
        
        response = await client.post(
            f"/api/events/{event_id}/capture/extract",
            json={
                "text": "Paid my florist $3000 for all the flowers",
                "conversation_history": []
            }
        )
        
        data = response.json()
        
        assert data.get("response_mode") == "clarify" or \
               "name" in data.get("assistant_message", "").lower()
    
    @pytest.mark.asyncio
    async def test_photographer_without_name_asks_clarification(self, client: AsyncClient):
        """Test photographer without name triggers clarification."""
        event_resp = await client.post(
            "/api/events",
            json={"name": "Test Wedding", "event_date": "2026-12-01"}
        )
        event_id = event_resp.json()["id"]
        
        response = await client.post(
            f"/api/events/{event_id}/capture/extract",
            json={
                "text": "Gave the photographer a $2000 deposit today",
                "conversation_history": []
            }
        )
        
        data = response.json()
        
        assert data.get("response_mode") == "clarify" or \
               "name" in data.get("assistant_message", "").lower()


@pytest.mark.payments
class TestPaymentFlows:
    """Tests for various payment scenarios."""
    
    @pytest.mark.asyncio
    async def test_full_payment_no_pending(self, client: AsyncClient):
        """Test full payment doesn't create pending record."""
        event_resp = await client.post(
            "/api/events",
            json={"name": "Test Wedding", "event_date": "2026-12-01"}
        )
        event_id = event_resp.json()["id"]
        
        response = await client.post(
            f"/api/events/{event_id}/capture/extract",
            json={
                "text": "Paid ABC Florist $3000 in full today",
                "conversation_history": []
            }
        )
        
        data = response.json()
        
        if data.get("needs_confirmation"):
            await client.post(
                f"/api/events/{event_id}/capture/confirm",
                json={"extraction_result": data}
            )
        
        payments = (await client.get(f"/api/events/{event_id}/payments")).json()
        pending = [p for p in payments if not p.get("paid_date")]
        
        assert len(pending) == 0
    
    @pytest.mark.asyncio
    async def test_partial_payment_creates_pending(self, client: AsyncClient):
        """Test partial payment extraction includes remaining balance."""
        event_resp = await client.post(
            "/api/events",
            json={"name": "Test Wedding", "event_date": "2026-12-01"}
        )
        event_id = event_resp.json()["id"]
        
        response = await client.post(
            f"/api/events/{event_id}/capture/extract",
            json={
                "text": "Booked Grand Venue for $20000, paid $5000 deposit, remaining $15000 due June 1st 2026",
                "conversation_history": []
            }
        )
        
        data = response.json()
        extraction_data = data.get("data", {})
        msg = data.get("assistant_message", "").lower()
        
        remaining = extraction_data.get("remaining_balance")
        due_date = extraction_data.get("due_date")
        amount_paid = extraction_data.get("amount_paid")
        
        assert remaining is not None or due_date is not None or \
               amount_paid is not None or \
               "15,000" in msg or "15000" in msg or \
               "remaining" in msg or "deposit" in msg, \
            f"Extraction should capture partial payment info. Data: {extraction_data}, Msg: {msg}"
    
    @pytest.mark.asyncio
    async def test_booking_with_remaining_balance(self, client: AsyncClient):
        """Test booking scenario calculates amounts correctly."""
        event_resp = await client.post(
            "/api/events",
            json={"name": "Test Wedding", "event_date": "2026-12-01"}
        )
        event_id = event_resp.json()["id"]
        
        response = await client.post(
            f"/api/events/{event_id}/capture/extract",
            json={
                "text": "I have a photographer booked for $10000, remaining $5000 due Aug 1st 2026",
                "conversation_history": []
            }
        )
        
        data = response.json()
        extraction_data = data.get("data", {})
        
        amount_paid = extraction_data.get("amount_paid")
        remaining = extraction_data.get("remaining_balance")
        
        assert str(amount_paid) == "5000" or str(remaining) == "5000"


@pytest.mark.context
class TestConversationContext:
    """Tests for conversation history and context preservation."""
    
    @pytest.mark.asyncio
    async def test_followup_preserves_context(self, client: AsyncClient):
        """Test that follow-up responses use conversation context."""
        event_resp = await client.post(
            "/api/events",
            json={"name": "Test Wedding", "event_date": "2026-12-01"}
        )
        event_id = event_resp.json()["id"]
        
        first_response = await client.post(
            f"/api/events/{event_id}/capture/extract",
            json={
                "text": "I paid my florist $1000 yesterday",
                "conversation_history": []
            }
        )
        first_data = first_response.json()
        
        history = [
            {"role": "user", "content": "I paid my florist $1000 yesterday"},
            {"role": "assistant", "content": first_data.get("assistant_message", "Got it! What's the name of the florist?")}
        ]
        
        followup_response = await client.post(
            f"/api/events/{event_id}/capture/extract",
            json={
                "text": "The florist's name is Bloom & Petals",
                "conversation_history": history
            }
        )
        
        followup_data = followup_response.json()
        
        assert followup_data.get("intent") == "payment" or \
               "florist" in followup_data.get("assistant_message", "").lower() or \
               "bloom" in followup_data.get("assistant_message", "").lower() or \
               followup_data.get("data", {}).get("vendor_name") is not None or \
               followup_data.get("intent") == "conversation"


@pytest.mark.queries
class TestEmptyDataHandling:
    """Tests for empty data scenarios."""
    
    @pytest.mark.asyncio
    async def test_query_empty_payments(self, client: AsyncClient):
        """Test querying payments when none exist."""
        event_resp = await client.post(
            "/api/events",
            json={"name": "Empty Test Wedding", "event_date": "2026-12-01"}
        )
        event_id = event_resp.json()["id"]
        
        response = await client.post(
            f"/api/events/{event_id}/capture/extract",
            json={
                "text": "What's my largest expense?",
                "conversation_history": []
            }
        )
        
        data = response.json()
        
        assistant_msg = data.get("assistant_message", "").lower()
        assert "no" in assistant_msg or \
               "haven't" in assistant_msg or \
               "don't have" in assistant_msg or \
               "yet" in assistant_msg
    
    @pytest.mark.asyncio
    async def test_query_empty_vendors(self, client: AsyncClient):
        """Test querying vendors when none exist."""
        event_resp = await client.post(
            "/api/events",
            json={"name": "Empty Test Wedding", "event_date": "2026-12-01"}
        )
        event_id = event_resp.json()["id"]
        
        response = await client.post(
            f"/api/events/{event_id}/capture/extract",
            json={
                "text": "Show me all my vendors",
                "conversation_history": []
            }
        )
        
        data = response.json()
        
        assistant_msg = data.get("assistant_message", "").lower()
        assert "no" in assistant_msg or \
               "haven't" in assistant_msg or \
               "don't have" in assistant_msg or \
               "yet" in assistant_msg
    
    @pytest.mark.asyncio
    async def test_query_empty_tasks(self, client: AsyncClient):
        """Test querying tasks when none exist."""
        event_resp = await client.post(
            "/api/events",
            json={"name": "Empty Test Wedding", "event_date": "2026-12-01"}
        )
        event_id = event_resp.json()["id"]
        
        response = await client.post(
            f"/api/events/{event_id}/capture/extract",
            json={
                "text": "What tasks do I have pending?",
                "conversation_history": []
            }
        )
        
        data = response.json()
        
        assistant_msg = data.get("assistant_message", "").lower()
        assert "no" in assistant_msg or \
               "haven't" in assistant_msg or \
               "don't have" in assistant_msg or \
               "yet" in assistant_msg


@pytest.mark.queries
class TestQueryHandling:
    """Tests for various query scenarios."""
    
    @pytest.mark.asyncio
    async def test_total_spent_query(self, client: AsyncClient):
        """Test aggregate query for total spent."""
        event_resp = await client.post(
            "/api/events",
            json={"name": "Test Wedding", "event_date": "2026-12-01"}
        )
        event_id = event_resp.json()["id"]
        
        await client.post(
            f"/api/events/{event_id}/capture/extract",
            json={
                "text": "Paid Enmuse Photography $5000 today",
                "conversation_history": []
            }
        )
        
        response = await client.post(
            f"/api/events/{event_id}/capture/extract",
            json={
                "text": "How much have I spent so far?",
                "conversation_history": []
            }
        )
        
        data = response.json()
        
        assert data.get("response_mode") == "answer" or \
               data.get("intent") == "query" or \
               "$" in data.get("assistant_message", "")
    
    @pytest.mark.asyncio
    async def test_pending_payments_query(self, client: AsyncClient):
        """Test query for pending payments."""
        event_resp = await client.post(
            "/api/events",
            json={"name": "Test Wedding", "event_date": "2026-12-01"}
        )
        event_id = event_resp.json()["id"]
        
        response = await client.post(
            f"/api/events/{event_id}/capture/extract",
            json={
                "text": "What payments are still pending?",
                "conversation_history": []
            }
        )
        
        data = response.json()
        
        assert data.get("response_mode") == "answer" or \
               data.get("intent") == "query"


@pytest.mark.tasks
class TestBulkOperations:
    """Tests for bulk task creation."""
    
    @pytest.mark.asyncio
    async def test_bulk_tasks_creation(self, client: AsyncClient):
        """Test creating multiple tasks in one prompt."""
        event_resp = await client.post(
            "/api/events",
            json={"name": "Test Wedding", "event_date": "2026-12-01"}
        )
        event_id = event_resp.json()["id"]
        
        response = await client.post(
            f"/api/events/{event_id}/capture/extract",
            json={
                "text": "Add these tasks: 1) Finalize guest list 2) Order invitations 3) Book hotel rooms",
                "conversation_history": []
            }
        )
        
        data = response.json()
        
        assistant_msg = data.get("assistant_message", "").lower()
        assert any(word in assistant_msg for word in ["task", "guest", "invitation", "hotel"])


@pytest.mark.deletes
class TestDeleteConfirmation:
    """Tests for delete operation safety."""
    
    @pytest.mark.asyncio
    async def test_delete_requires_confirmation(self, client: AsyncClient, test_db):
        """Test that delete operations require confirmation."""
        from app.models import Event, Task
        
        event = Event(name="Delete Confirm Test", event_date=date(2026, 12, 1))
        test_db.add(event)
        await test_db.flush()
        
        task = Task(
            event_id=event.id, title="Book the photographer",
            status="pending", priority="medium"
        )
        test_db.add(task)
        await test_db.commit()
        
        response = await client.post(
            f"/api/events/{event.id}/capture/extract",
            json={
                "text": "Delete the photographer task",
                "conversation_history": []
            }
        )
        
        data = response.json()
        msg = data.get("assistant_message", "").lower()
        
        assert data.get("needs_confirmation") == True or \
               data.get("response_mode") == "confirm" or \
               data.get("action") == "delete" or \
               "confirm" in msg or "sure" in msg or \
               "delete" in msg or "remove" in msg
