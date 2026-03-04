from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.event import Event
from app.models.task import Task
from app.schemas.task import TaskCreate, TaskUpdate, TaskResponse

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


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    event_id: str,
    task_data: TaskCreate,
    db: AsyncSession = Depends(get_db),
) -> Task:
    """Create a new task for an event."""
    await get_event_or_404(event_id, db)
    
    task = Task(event_id=event_id, **task_data.model_dump())
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


@router.get("", response_model=List[TaskResponse])
async def list_tasks(
    event_id: str,
    db: AsyncSession = Depends(get_db),
) -> List[Task]:
    """List all tasks for an event."""
    await get_event_or_404(event_id, db)
    
    result = await db.execute(
        select(Task)
        .where(Task.event_id == event_id)
        .order_by(Task.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    event_id: str,
    task_id: str,
    db: AsyncSession = Depends(get_db),
) -> Task:
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
    return task


@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    event_id: str,
    task_id: str,
    task_data: TaskUpdate,
    db: AsyncSession = Depends(get_db),
) -> Task:
    """Update a task."""
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
    
    update_data = task_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(task, field, value)
    
    await db.commit()
    await db.refresh(task)
    return task


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
