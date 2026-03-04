from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.event import Event
from app.models.vendor import Vendor
from app.schemas.vendor import VendorCreate, VendorUpdate, VendorResponse

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


@router.post("", response_model=VendorResponse, status_code=status.HTTP_201_CREATED)
async def create_vendor(
    event_id: str,
    vendor_data: VendorCreate,
    db: AsyncSession = Depends(get_db),
) -> Vendor:
    """Create a new vendor for an event."""
    await get_event_or_404(event_id, db)
    
    vendor = Vendor(event_id=event_id, **vendor_data.model_dump())
    db.add(vendor)
    await db.commit()
    await db.refresh(vendor)
    return vendor


@router.get("", response_model=List[VendorResponse])
async def list_vendors(
    event_id: str,
    db: AsyncSession = Depends(get_db),
) -> List[Vendor]:
    """List all vendors for an event."""
    await get_event_or_404(event_id, db)
    
    result = await db.execute(
        select(Vendor)
        .where(Vendor.event_id == event_id)
        .order_by(Vendor.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/{vendor_id}", response_model=VendorResponse)
async def get_vendor(
    event_id: str,
    vendor_id: str,
    db: AsyncSession = Depends(get_db),
) -> Vendor:
    """Get a vendor by ID."""
    await get_event_or_404(event_id, db)
    
    result = await db.execute(
        select(Vendor).where(Vendor.id == vendor_id, Vendor.event_id == event_id)
    )
    vendor = result.scalar_one_or_none()
    if not vendor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vendor not found",
        )
    return vendor


@router.put("/{vendor_id}", response_model=VendorResponse)
async def update_vendor(
    event_id: str,
    vendor_id: str,
    vendor_data: VendorUpdate,
    db: AsyncSession = Depends(get_db),
) -> Vendor:
    """Update a vendor."""
    await get_event_or_404(event_id, db)
    
    result = await db.execute(
        select(Vendor).where(Vendor.id == vendor_id, Vendor.event_id == event_id)
    )
    vendor = result.scalar_one_or_none()
    if not vendor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vendor not found",
        )
    
    update_data = vendor_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(vendor, field, value)
    
    await db.commit()
    await db.refresh(vendor)
    return vendor


@router.delete("/{vendor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vendor(
    event_id: str,
    vendor_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a vendor."""
    await get_event_or_404(event_id, db)
    
    result = await db.execute(
        select(Vendor).where(Vendor.id == vendor_id, Vendor.event_id == event_id)
    )
    vendor = result.scalar_one_or_none()
    if not vendor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vendor not found",
        )
    
    await db.delete(vendor)
    await db.commit()
