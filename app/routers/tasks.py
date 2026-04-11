import logging
from datetime import date
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.event import Event
from app.models.task import Task, TaskStatus
from app.models.vendor import Vendor
from app.models.payment import Payment
from app.schemas.task import TaskCreate, TaskUpdate, TaskResponse

logger = logging.getLogger(__name__)
router = APIRouter()


async def get_event_or_404(event_id: str, db: AsyncSession) -> Event:
    """Get an event by ID or raise 404."""
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )
    return event


def _task_to_response(task: Task, vendor_name: str | None = None) -> dict:
    """Build a TaskResponse-compatible dict with vendor_name resolved."""
    return {
        "id": task.id,
        "event_id": task.event_id,
        "vendor_id": task.vendor_id,
        "vendor_category": task.vendor_category,
        "vendor_name": vendor_name,
        "title": task.title,
        "description": task.description,
        "assignee": task.assignee,
        "due_date": task.due_date,
        "due_time": task.due_time,
        "status": task.status,
        "priority": task.priority,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    }


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    event_id: str,
    task_data: TaskCreate,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create a new task for an event."""
    await get_event_or_404(event_id, db)
    
    task = Task(event_id=event_id, **task_data.model_dump())
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return _task_to_response(task)


@router.get("", response_model=List[TaskResponse])
async def list_tasks(
    event_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """List all tasks for an event with vendor names resolved."""
    await get_event_or_404(event_id, db)
    
    result = await db.execute(
        select(Task)
        .where(Task.event_id == event_id)
        .order_by(Task.created_at.desc())
    )
    tasks = list(result.scalars().all())
    
    vendor_ids = {t.vendor_id for t in tasks if t.vendor_id}
    vendor_map: dict[str, str] = {}
    if vendor_ids:
        v_result = await db.execute(
            select(Vendor).where(Vendor.id.in_(vendor_ids))
        )
        for v in v_result.scalars().all():
            vendor_map[v.id] = v.name
    
    return [
        _task_to_response(t, vendor_map.get(t.vendor_id) if t.vendor_id else None)
        for t in tasks
    ]


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    event_id: str,
    task_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get a task by ID."""
    await get_event_or_404(event_id, db)
    
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.event_id == event_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )
    
    vendor_name = None
    if task.vendor_id:
        v_result = await db.execute(select(Vendor).where(Vendor.id == task.vendor_id))
        vendor = v_result.scalar_one_or_none()
        vendor_name = vendor.name if vendor else None
    
    return _task_to_response(task, vendor_name)


@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    event_id: str,
    task_id: str,
    task_data: TaskUpdate,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Update a task. Syncs linked payment status when a payment-reminder task is completed or un-completed."""
    await get_event_or_404(event_id, db)
    
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.event_id == event_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )
    
    old_status = task.status
    update_data = task_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(task, field, value)
    
    new_status = task.status
    
    if old_status != new_status and task.vendor_id:
        await _sync_payment_for_task(task, old_status, new_status, db)
    
    await db.commit()
    await db.refresh(task)
    
    vendor_name = None
    if task.vendor_id:
        v_result = await db.execute(select(Vendor).where(Vendor.id == task.vendor_id))
        vendor = v_result.scalar_one_or_none()
        vendor_name = vendor.name if vendor else None
    
    return _task_to_response(task, vendor_name)


async def _sync_payment_for_task(
    task: Task,
    old_status: TaskStatus,
    new_status: TaskStatus,
    db: AsyncSession,
) -> None:
    """When a payment-reminder task is moved to Done, mark the matching payment as paid. Reverse on undo."""
    if new_status == TaskStatus.COMPLETED and old_status != TaskStatus.COMPLETED:
        query = select(Payment).where(
            Payment.event_id == task.event_id,
            Payment.vendor_id == task.vendor_id,
            Payment.paid_date.is_(None),
        )
        if task.due_date:
            query = query.where(Payment.due_date == task.due_date)
        
        p_result = await db.execute(query)
        payment = p_result.scalars().first()
        if payment:
            payment.paid_date = date.today()
            logger.info(f"Marked payment {payment.id} as paid (task {task.id} completed)")
    
    elif old_status == TaskStatus.COMPLETED and new_status != TaskStatus.COMPLETED:
        query = select(Payment).where(
            Payment.event_id == task.event_id,
            Payment.vendor_id == task.vendor_id,
            Payment.paid_date.isnot(None),
        )
        if task.due_date:
            query = query.where(Payment.due_date == task.due_date)
        
        p_result = await db.execute(query.order_by(Payment.paid_date.desc()))
        payment = p_result.scalars().first()
        if payment:
            payment.paid_date = None
            logger.info(f"Reversed payment {payment.id} to unpaid (task {task.id} un-completed)")


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    event_id: str,
    task_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a task."""
    await get_event_or_404(event_id, db)
    
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.event_id == event_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )
    
    await db.delete(task)
    await db.commit()
