from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.event import Event
from app.models.payment import Payment
from app.schemas.payment import PaymentCreate, PaymentUpdate, PaymentResponse

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


@router.post("", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_payment(
    event_id: str,
    payment_data: PaymentCreate,
    db: AsyncSession = Depends(get_db),
) -> Payment:
    """Create a new payment for an event."""
    await get_event_or_404(event_id, db)
    
    payment = Payment(event_id=event_id, **payment_data.model_dump())
    db.add(payment)
    await db.commit()
    await db.refresh(payment)
    return payment


@router.get("", response_model=List[PaymentResponse])
async def list_payments(
    event_id: str,
    db: AsyncSession = Depends(get_db),
) -> List[Payment]:
    """List all payments for an event."""
    await get_event_or_404(event_id, db)
    
    result = await db.execute(
        select(Payment)
        .where(Payment.event_id == event_id)
        .order_by(Payment.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment(
    event_id: str,
    payment_id: str,
    db: AsyncSession = Depends(get_db),
) -> Payment:
    """Get a payment by ID."""
    await get_event_or_404(event_id, db)
    
    result = await db.execute(
        select(Payment).where(Payment.id == payment_id, Payment.event_id == event_id)
    )
    payment = result.scalar_one_or_none()
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )
    return payment


@router.put("/{payment_id}", response_model=PaymentResponse)
async def update_payment(
    event_id: str,
    payment_id: str,
    payment_data: PaymentUpdate,
    db: AsyncSession = Depends(get_db),
) -> Payment:
    """Update a payment."""
    await get_event_or_404(event_id, db)
    
    result = await db.execute(
        select(Payment).where(Payment.id == payment_id, Payment.event_id == event_id)
    )
    payment = result.scalar_one_or_none()
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )
    
    update_data = payment_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(payment, field, value)
    
    await db.commit()
    await db.refresh(payment)
    return payment


@router.delete("/{payment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_payment(
    event_id: str,
    payment_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a payment."""
    await get_event_or_404(event_id, db)
    
    result = await db.execute(
        select(Payment).where(Payment.id == payment_id, Payment.event_id == event_id)
    )
    payment = result.scalar_one_or_none()
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )
    
    await db.delete(payment)
    await db.commit()
