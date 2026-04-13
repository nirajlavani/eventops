import os
import uuid
import logging
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File, Form, Query, status
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

logger = logging.getLogger(__name__)

from app.config import get_settings
from app.database import get_db
from app.models.event import Event
from app.models.vendor import Vendor
from app.models.payment import Payment
from app.models.attachment import Attachment
from app.schemas.attachment import AttachmentResponse, AttachmentUpdate

router = APIRouter()

_indexing_status: Dict[str, dict] = {}

ALLOWED_EXTENSIONS = {
    "pdf", "jpg", "jpeg", "png", "gif", "webp",
    "doc", "docx", "xls", "xlsx", "csv", "txt",
}


def _get_upload_dir(event_id: str) -> Path:
    settings = get_settings()
    upload_path = Path(settings.upload_dir) / event_id
    upload_path.mkdir(parents=True, exist_ok=True)
    return upload_path


def _validate_file(filename: str, size: int) -> None:
    settings = get_settings()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type '.{ext}' not allowed. Accepted: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    if size > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File exceeds maximum size of {settings.max_upload_size_mb} MB",
        )


def _sanitize_filename(filename: str) -> str:
    safe = "".join(c if c.isalnum() or c in "._- " else "_" for c in filename)
    return safe.strip()


async def _get_event_or_404(event_id: str, db: AsyncSession) -> Event:
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return event


def _enrich_response(attachment: Attachment) -> AttachmentResponse:
    vendor_name = attachment.vendor.name if attachment.vendor else None
    payment_desc = None
    if attachment.payment:
        p = attachment.payment
        vendor = p.vendor
        payment_desc = f"${p.amount}" + (f" - {vendor.name}" if vendor else "")

    return AttachmentResponse(
        id=attachment.id,
        event_id=attachment.event_id,
        vendor_id=attachment.vendor_id,
        payment_id=attachment.payment_id,
        filename=attachment.filename,
        original_filename=attachment.original_filename,
        content_type=attachment.content_type,
        file_size=attachment.file_size,
        category=attachment.category,
        description=attachment.description,
        created_at=attachment.created_at,
        updated_at=attachment.updated_at,
        vendor_name=vendor_name,
        payment_description=payment_desc,
    )


@router.post("", response_model=AttachmentResponse, status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    event_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    description: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    vendor_id: Optional[str] = Form(None),
    payment_id: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
) -> AttachmentResponse:
    """Upload a file attachment for an event."""
    await _get_event_or_404(event_id, db)

    contents = await file.read()
    _validate_file(file.filename or "unknown", len(contents))

    if vendor_id:
        result = await db.execute(
            select(Vendor).where(Vendor.id == vendor_id, Vendor.event_id == event_id)
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Vendor not found in this event")

    if payment_id:
        result = await db.execute(
            select(Payment).where(Payment.id == payment_id, Payment.event_id == event_id)
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payment not found in this event")

    original = file.filename or "unknown"
    ext = original.rsplit(".", 1)[-1].lower() if "." in original else ""
    stored_name = f"{uuid.uuid4().hex}_{_sanitize_filename(original)}"

    upload_dir = _get_upload_dir(event_id)
    file_path = upload_dir / stored_name

    with open(file_path, "wb") as f:
        f.write(contents)

    attachment = Attachment(
        event_id=event_id,
        vendor_id=vendor_id,
        payment_id=payment_id,
        filename=stored_name,
        original_filename=original,
        file_path=str(file_path),
        content_type=file.content_type,
        file_size=len(contents),
        category=category,
        description=description,
    )
    db.add(attachment)
    await db.commit()

    result = await db.execute(
        select(Attachment)
        .options(selectinload(Attachment.vendor), selectinload(Attachment.payment).selectinload(Payment.vendor))
        .where(Attachment.id == attachment.id)
    )
    attachment = result.scalar_one()

    logger.info(
        "Uploaded attachment: id=%s event=%s file=%s size=%d ext=%s",
        attachment.id, event_id, original, len(contents), ext,
    )

    if ext == "pdf":
        _indexing_status[attachment.id] = {"stage": "pending", "percent": 0}
        logger.info("Queuing PDF indexing for attachment %s", attachment.id)
        background_tasks.add_task(
            _run_indexing, event_id, attachment.id,
            str(file_path), original,
            attachment.vendor.name if attachment.vendor else None,
        )

    return _enrich_response(attachment)


async def _run_indexing(
    event_id: str, att_id: str, file_path: str, doc_name: str, vendor_name: Optional[str],
) -> None:
    """Background task: index a PDF into the vector store with progress tracking."""
    try:
        from app.retrieval.rag_service import RAGService
        rag = RAGService()

        def _on_progress(stage: str, pct: int) -> None:
            _indexing_status[att_id] = {"stage": stage, "percent": pct}
            logger.info("Indexing %s: %s (%d%%)", doc_name, stage, pct)

        count = await rag.index_document(
            event_id=event_id,
            attachment_id=att_id,
            file_path=file_path,
            document_name=doc_name,
            vendor_name=vendor_name,
            on_progress=_on_progress,
        )
        _indexing_status[att_id] = {"stage": "done", "percent": 100, "chunks": count}
        logger.info("Indexed PDF %s: %d chunks", doc_name, count)
    except Exception as e:
        _indexing_status[att_id] = {"stage": "error", "percent": 0, "error": str(e)}
        logger.error("Failed to index PDF %s: %s", doc_name, str(e), exc_info=True)


@router.get("/{attachment_id}/indexing-status")
async def get_indexing_status(attachment_id: str) -> JSONResponse:
    """Return the current indexing progress for a PDF attachment."""
    status = _indexing_status.get(attachment_id)
    if status is None:
        return JSONResponse({"stage": "none", "percent": 0})
    return JSONResponse(status)


@router.get("", response_model=List[AttachmentResponse])
async def list_attachments(
    event_id: str,
    vendor_id: Optional[str] = Query(None),
    payment_id: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    sort_by: Optional[str] = Query("created_at", regex="^(created_at|original_filename|file_size|category)$"),
    sort_order: Optional[str] = Query("desc", regex="^(asc|desc)$"),
    db: AsyncSession = Depends(get_db),
) -> List[AttachmentResponse]:
    """List attachments with optional filtering and sorting."""
    await _get_event_or_404(event_id, db)

    query = (
        select(Attachment)
        .options(selectinload(Attachment.vendor), selectinload(Attachment.payment).selectinload(Payment.vendor))
        .where(Attachment.event_id == event_id)
    )

    if vendor_id:
        query = query.where(Attachment.vendor_id == vendor_id)
    if payment_id:
        query = query.where(Attachment.payment_id == payment_id)
    if category:
        query = query.where(Attachment.category == category)

    sort_col = getattr(Attachment, sort_by, Attachment.created_at)
    if sort_order == "asc":
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

    result = await db.execute(query)
    attachments = list(result.scalars().all())
    return [_enrich_response(a) for a in attachments]


@router.get("/{attachment_id}", response_model=AttachmentResponse)
async def get_attachment(
    event_id: str,
    attachment_id: str,
    db: AsyncSession = Depends(get_db),
) -> AttachmentResponse:
    """Get attachment metadata."""
    await _get_event_or_404(event_id, db)

    result = await db.execute(
        select(Attachment)
        .options(selectinload(Attachment.vendor), selectinload(Attachment.payment).selectinload(Payment.vendor))
        .where(Attachment.id == attachment_id, Attachment.event_id == event_id)
    )
    attachment = result.scalar_one_or_none()
    if not attachment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")
    return _enrich_response(attachment)


@router.get("/{attachment_id}/download")
async def download_attachment(
    event_id: str,
    attachment_id: str,
    inline: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    """Download or preview the actual file.

    Pass ?inline=true to serve the file for in-browser preview
    (Content-Disposition: inline) instead of forcing a download.
    """
    await _get_event_or_404(event_id, db)

    result = await db.execute(
        select(Attachment).where(Attachment.id == attachment_id, Attachment.event_id == event_id)
    )
    attachment = result.scalar_one_or_none()
    if not attachment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")

    file_path = Path(attachment.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found on disk")

    media = attachment.content_type or "application/octet-stream"

    if inline:
        return FileResponse(
            path=str(file_path),
            media_type=media,
            content_disposition_type="inline",
        )

    return FileResponse(
        path=str(file_path),
        filename=attachment.original_filename,
        media_type=media,
    )


@router.put("/{attachment_id}", response_model=AttachmentResponse)
async def update_attachment(
    event_id: str,
    attachment_id: str,
    update_data: AttachmentUpdate,
    db: AsyncSession = Depends(get_db),
) -> AttachmentResponse:
    """Update attachment metadata (description, category, vendor/payment link)."""
    await _get_event_or_404(event_id, db)

    result = await db.execute(
        select(Attachment).where(Attachment.id == attachment_id, Attachment.event_id == event_id)
    )
    attachment = result.scalar_one_or_none()
    if not attachment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")

    data = update_data.model_dump(exclude_unset=True)

    if "vendor_id" in data and data["vendor_id"]:
        r = await db.execute(
            select(Vendor).where(Vendor.id == data["vendor_id"], Vendor.event_id == event_id)
        )
        if not r.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Vendor not found in this event")

    if "payment_id" in data and data["payment_id"]:
        r = await db.execute(
            select(Payment).where(Payment.id == data["payment_id"], Payment.event_id == event_id)
        )
        if not r.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payment not found in this event")

    for field, value in data.items():
        setattr(attachment, field, value)

    await db.commit()

    result = await db.execute(
        select(Attachment)
        .options(selectinload(Attachment.vendor), selectinload(Attachment.payment).selectinload(Payment.vendor))
        .where(Attachment.id == attachment_id)
    )
    attachment = result.scalar_one()
    return _enrich_response(attachment)


@router.delete("/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_attachment(
    event_id: str,
    attachment_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete an attachment (file on disk and DB record)."""
    await _get_event_or_404(event_id, db)

    result = await db.execute(
        select(Attachment).where(Attachment.id == attachment_id, Attachment.event_id == event_id)
    )
    attachment = result.scalar_one_or_none()
    if not attachment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")

    try:
        from app.retrieval.rag_service import RAGService
        rag = RAGService()
        removed = rag.delete_document(event_id, attachment_id)
        logger.info("Deleted %d indexed chunks for attachment %s", removed, attachment_id)
    except Exception as e:
        logger.error(
            "Failed to remove indexed chunks: attachment=%s error=%s",
            attachment_id, str(e), exc_info=True,
        )

    file_path = Path(attachment.file_path)
    if file_path.exists():
        os.remove(file_path)

    logger.info("Deleted attachment %s from event %s", attachment_id, event_id)
    await db.delete(attachment)
    await db.commit()
