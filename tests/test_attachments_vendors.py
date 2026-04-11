"""
Tests for Attachment CRUD and Vendor notes update.

All tests are deterministic (no LLM calls) and use the standard
client + test_db fixture pattern from conftest.py.
"""
import io
import os
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Event, Vendor, Payment
from app.models.attachment import Attachment


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_file(name: str = "test.pdf", content: bytes = b"%PDF-fake-content"):
    """Return a tuple suitable for httpx multipart upload."""
    return ("file", (name, io.BytesIO(content), "application/pdf"))


async def _create_event(db: AsyncSession) -> Event:
    event = Event(name="Attachment Test Event", event_date=date(2026, 9, 1))
    db.add(event)
    await db.flush()
    return event


async def _create_vendor(db: AsyncSession, event_id: str, name: str = "Test Vendor") -> Vendor:
    vendor = Vendor(event_id=event_id, name=name, category="venue")
    db.add(vendor)
    await db.flush()
    return vendor


async def _create_payment(db: AsyncSession, event_id: str, vendor_id: str) -> Payment:
    payment = Payment(
        event_id=event_id,
        vendor_id=vendor_id,
        amount=Decimal("5000"),
        paid_date=date(2026, 8, 1),
        method="check",
    )
    db.add(payment)
    await db.flush()
    return payment


async def _upload_file(
    client: AsyncClient,
    event_id: str,
    filename: str = "invoice.pdf",
    content: bytes = b"%PDF-test-data",
    **form_fields,
):
    """Upload a file and return the response."""
    files = {"file": (filename, io.BytesIO(content), "application/pdf")}
    data = {k: v for k, v in form_fields.items() if v is not None}
    return await client.post(
        f"/api/events/{event_id}/attachments",
        files=files,
        data=data,
    )


# ===========================================================================
# 1. UPLOAD
# ===========================================================================

@pytest.mark.attachments
@pytest.mark.fast
class TestAttachmentUpload:
    """Covers POST /api/events/{eid}/attachments."""

    @pytest.fixture
    async def setup(self, client: AsyncClient, test_db: AsyncSession):
        event = await _create_event(test_db)
        vendor = await _create_vendor(test_db, event.id)
        payment = await _create_payment(test_db, event.id, vendor.id)
        await test_db.commit()
        return {"event_id": event.id, "vendor_id": vendor.id, "payment_id": payment.id, "db": test_db}

    @pytest.mark.asyncio
    async def test_upload_valid_file(self, client: AsyncClient, setup: dict):
        resp = await _upload_file(client, setup["event_id"])
        assert resp.status_code == 201
        data = resp.json()
        assert data["original_filename"] == "invoice.pdf"
        assert data["event_id"] == setup["event_id"]
        assert data["file_size"] > 0
        assert "id" in data

    @pytest.mark.asyncio
    async def test_upload_with_vendor(self, client: AsyncClient, setup: dict):
        resp = await _upload_file(
            client, setup["event_id"],
            vendor_id=setup["vendor_id"],
            category="contract",
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["vendor_id"] == setup["vendor_id"]
        assert data["vendor_name"] is not None
        assert data["category"] == "contract"

    @pytest.mark.asyncio
    async def test_upload_with_payment(self, client: AsyncClient, setup: dict):
        resp = await _upload_file(
            client, setup["event_id"],
            payment_id=setup["payment_id"],
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["payment_id"] == setup["payment_id"]
        assert data["payment_description"] is not None

    @pytest.mark.asyncio
    async def test_reject_disallowed_extension(self, client: AsyncClient, setup: dict):
        files = {"file": ("malware.exe", io.BytesIO(b"bad"), "application/octet-stream")}
        resp = await client.post(
            f"/api/events/{setup['event_id']}/attachments",
            files=files,
        )
        assert resp.status_code == 400
        assert "not allowed" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_reject_nonexistent_event(self, client: AsyncClient):
        resp = await _upload_file(client, "nonexistent-event-id")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_reject_invalid_vendor(self, client: AsyncClient, setup: dict):
        resp = await _upload_file(
            client, setup["event_id"],
            vendor_id="bad-vendor-id",
        )
        assert resp.status_code == 400


# ===========================================================================
# 2. LIST / FILTER / SORT
# ===========================================================================

@pytest.mark.attachments
@pytest.mark.fast
class TestAttachmentList:
    """Covers GET /api/events/{eid}/attachments with filters and sorting."""

    @pytest.fixture
    async def setup(self, client: AsyncClient, test_db: AsyncSession):
        event = await _create_event(test_db)
        vendor = await _create_vendor(test_db, event.id)
        await test_db.commit()
        eid = event.id

        await _upload_file(client, eid, filename="alpha.pdf", content=b"A" * 100, vendor_id=vendor.id, category="contract")
        await _upload_file(client, eid, filename="beta.png", content=b"B" * 500, vendor_id=vendor.id, category="photo")
        await _upload_file(client, eid, filename="gamma.txt", content=b"C" * 10, category="receipt")

        return {"event_id": eid, "vendor_id": vendor.id}

    @pytest.mark.asyncio
    async def test_list_all(self, client: AsyncClient, setup: dict):
        resp = await client.get(f"/api/events/{setup['event_id']}/attachments")
        assert resp.status_code == 200
        assert len(resp.json()) == 3

    @pytest.mark.asyncio
    async def test_filter_by_vendor(self, client: AsyncClient, setup: dict):
        resp = await client.get(
            f"/api/events/{setup['event_id']}/attachments",
            params={"vendor_id": setup["vendor_id"]},
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    @pytest.mark.asyncio
    async def test_filter_by_category(self, client: AsyncClient, setup: dict):
        resp = await client.get(
            f"/api/events/{setup['event_id']}/attachments",
            params={"category": "receipt"},
        )
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        assert items[0]["category"] == "receipt"

    @pytest.mark.asyncio
    async def test_sort_by_filename_asc(self, client: AsyncClient, setup: dict):
        resp = await client.get(
            f"/api/events/{setup['event_id']}/attachments",
            params={"sort_by": "original_filename", "sort_order": "asc"},
        )
        names = [a["original_filename"] for a in resp.json()]
        assert names == sorted(names)

    @pytest.mark.asyncio
    async def test_sort_by_filesize_desc(self, client: AsyncClient, setup: dict):
        resp = await client.get(
            f"/api/events/{setup['event_id']}/attachments",
            params={"sort_by": "file_size", "sort_order": "desc"},
        )
        sizes = [a["file_size"] for a in resp.json()]
        assert sizes == sorted(sizes, reverse=True)


# ===========================================================================
# 3. GET & DOWNLOAD
# ===========================================================================

@pytest.mark.attachments
@pytest.mark.fast
class TestAttachmentGetAndDownload:
    """Covers GET .../attachments/{id} and GET .../attachments/{id}/download."""

    @pytest.fixture
    async def setup(self, client: AsyncClient, test_db: AsyncSession):
        event = await _create_event(test_db)
        await test_db.commit()
        file_content = b"download-me-content-1234"
        resp = await _upload_file(client, event.id, filename="readme.txt", content=file_content)
        attachment = resp.json()
        return {"event_id": event.id, "attachment_id": attachment["id"], "content": file_content, "db": test_db}

    @pytest.mark.asyncio
    async def test_get_metadata(self, client: AsyncClient, setup: dict):
        resp = await client.get(
            f"/api/events/{setup['event_id']}/attachments/{setup['attachment_id']}"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == setup["attachment_id"]
        assert data["original_filename"] == "readme.txt"
        assert "created_at" in data
        assert "updated_at" in data

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_404(self, client: AsyncClient, setup: dict):
        resp = await client.get(
            f"/api/events/{setup['event_id']}/attachments/nonexistent-id"
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_download_returns_file_content(self, client: AsyncClient, setup: dict):
        resp = await client.get(
            f"/api/events/{setup['event_id']}/attachments/{setup['attachment_id']}/download"
        )
        assert resp.status_code == 200
        assert resp.content == setup["content"]

    @pytest.mark.asyncio
    async def test_download_missing_disk_file_returns_404(self, client: AsyncClient, setup: dict):
        result = await setup["db"].execute(
            select(Attachment).where(Attachment.id == setup["attachment_id"])
        )
        attachment = result.scalar_one()
        file_path = Path(attachment.file_path)
        if file_path.exists():
            os.remove(file_path)

        resp = await client.get(
            f"/api/events/{setup['event_id']}/attachments/{setup['attachment_id']}/download"
        )
        assert resp.status_code == 404


# ===========================================================================
# 4. UPDATE METADATA
# ===========================================================================

@pytest.mark.attachments
@pytest.mark.fast
class TestAttachmentUpdate:
    """Covers PUT .../attachments/{id}."""

    @pytest.fixture
    async def setup(self, client: AsyncClient, test_db: AsyncSession):
        event = await _create_event(test_db)
        vendor = await _create_vendor(test_db, event.id, name="Update Vendor")
        await test_db.commit()
        resp = await _upload_file(client, event.id)
        attachment = resp.json()
        return {"event_id": event.id, "vendor_id": vendor.id, "attachment_id": attachment["id"], "db": test_db}

    @pytest.mark.asyncio
    async def test_update_description_and_category(self, client: AsyncClient, setup: dict):
        resp = await client.put(
            f"/api/events/{setup['event_id']}/attachments/{setup['attachment_id']}",
            json={"description": "Updated desc", "category": "receipt"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["description"] == "Updated desc"
        assert data["category"] == "receipt"

    @pytest.mark.asyncio
    async def test_link_to_vendor(self, client: AsyncClient, setup: dict):
        resp = await client.put(
            f"/api/events/{setup['event_id']}/attachments/{setup['attachment_id']}",
            json={"vendor_id": setup["vendor_id"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["vendor_id"] == setup["vendor_id"]
        assert data["vendor_name"] == "Update Vendor"

    @pytest.mark.asyncio
    async def test_reject_invalid_vendor(self, client: AsyncClient, setup: dict):
        resp = await client.put(
            f"/api/events/{setup['event_id']}/attachments/{setup['attachment_id']}",
            json={"vendor_id": "bad-vendor-id"},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_update_nonexistent_returns_404(self, client: AsyncClient, setup: dict):
        resp = await client.put(
            f"/api/events/{setup['event_id']}/attachments/nonexistent-id",
            json={"description": "nope"},
        )
        assert resp.status_code == 404


# ===========================================================================
# 5. DELETE
# ===========================================================================

@pytest.mark.attachments
@pytest.mark.fast
class TestAttachmentDelete:
    """Covers DELETE .../attachments/{id}."""

    @pytest.fixture
    async def setup(self, client: AsyncClient, test_db: AsyncSession):
        event = await _create_event(test_db)
        await test_db.commit()
        resp = await _upload_file(client, event.id, filename="deleteme.pdf", content=b"trash")
        attachment = resp.json()
        return {"event_id": event.id, "attachment_id": attachment["id"], "db": test_db}

    @pytest.mark.asyncio
    async def test_delete_removes_record_and_file(self, client: AsyncClient, setup: dict):
        att_id = setup["attachment_id"]
        eid = setup["event_id"]
        db = setup["db"]

        result = await db.execute(select(Attachment).where(Attachment.id == att_id))
        attachment = result.scalar_one()
        file_on_disk = Path(attachment.file_path)
        assert file_on_disk.exists(), "File should exist before delete"

        resp = await client.delete(f"/api/events/{eid}/attachments/{att_id}")
        assert resp.status_code == 204

        assert not file_on_disk.exists(), "File should be removed from disk"

        result = await db.execute(select(Attachment).where(Attachment.id == att_id))
        assert result.scalar_one_or_none() is None, "DB row should be gone"

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_404(self, client: AsyncClient, setup: dict):
        resp = await client.delete(
            f"/api/events/{setup['event_id']}/attachments/nonexistent-id"
        )
        assert resp.status_code == 404


# ===========================================================================
# 6. VENDOR NOTES UPDATE
# ===========================================================================

@pytest.mark.vendors
@pytest.mark.fast
class TestVendorNotesUpdate:
    """Covers PUT /api/events/{eid}/vendors/{vid} -- notes field."""

    @pytest.fixture
    async def setup(self, client: AsyncClient, test_db: AsyncSession):
        event = await _create_event(test_db)
        vendor = await _create_vendor(test_db, event.id, name="Notes Vendor")
        await test_db.commit()
        return {"event_id": event.id, "vendor_id": vendor.id, "db": test_db}

    @pytest.mark.asyncio
    async def test_update_notes(self, client: AsyncClient, setup: dict):
        resp = await client.put(
            f"/api/events/{setup['event_id']}/vendors/{setup['vendor_id']}",
            json={"notes": "Great to work with, responsive."},
        )
        assert resp.status_code == 200
        assert resp.json()["notes"] == "Great to work with, responsive."

    @pytest.mark.asyncio
    async def test_notes_persisted_in_db(self, client: AsyncClient, setup: dict):
        await client.put(
            f"/api/events/{setup['event_id']}/vendors/{setup['vendor_id']}",
            json={"notes": "DB persistence check"},
        )
        result = await setup["db"].execute(
            select(Vendor).where(Vendor.id == setup["vendor_id"])
        )
        vendor = result.scalar_one()
        assert vendor.notes == "DB persistence check"

    @pytest.mark.asyncio
    async def test_clear_notes(self, client: AsyncClient, setup: dict):
        await client.put(
            f"/api/events/{setup['event_id']}/vendors/{setup['vendor_id']}",
            json={"notes": "Something"},
        )
        resp = await client.put(
            f"/api/events/{setup['event_id']}/vendors/{setup['vendor_id']}",
            json={"notes": ""},
        )
        assert resp.status_code == 200
        assert resp.json()["notes"] == ""
