from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.event import Event
from app.services.extraction import ExtractionService, get_extraction_service
from app.schemas.capture import (
    CaptureRequest,
    CaptureResponse,
    ConfirmRequest,
    ConfirmResponse,
    IntentType,
    PaymentData,
    TaskData,
    CalendarEventData,
    VendorData,
    UnknownData,
)

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


@router.post("/extract", response_model=CaptureResponse)
async def extract_from_text(
    event_id: str,
    request: CaptureRequest,
    db: AsyncSession = Depends(get_db),
    extraction_service: ExtractionService = Depends(get_extraction_service),
) -> CaptureResponse:
    """
    Extract structured data from natural language text.
    
    The LLM will classify the intent (payment, task, calendar_event, vendor, unknown)
    and extract relevant fields. The extracted data is returned for user
    confirmation before being persisted.
    
    Response includes:
    - intent: The classified intent type
    - confidence: Model confidence (0.0 - 1.0)
    - data: Extracted structured fields
    - missing_fields: Required fields that couldn't be extracted
    - needs_confirmation: Whether user should review before saving
    """
    await get_event_or_404(event_id, db)
    
    result, log_id = await extraction_service.extract(
        user_input=request.text,
        event_id=event_id,
        db=db,
    )
    
    intent_str = result.get("intent", "unknown")
    try:
        intent = IntentType(intent_str)
    except ValueError:
        intent = IntentType.UNKNOWN
    
    data = result.get("data", {})
    missing_fields = result.get("missing_fields", [])
    needs_confirmation = result.get("needs_confirmation", True)
    
    if intent == IntentType.PAYMENT:
        parsed_data = PaymentData(**data)
    elif intent == IntentType.TASK:
        parsed_data = TaskData(**data)
    elif intent == IntentType.CALENDAR_EVENT:
        parsed_data = CalendarEventData(**data)
    elif intent == IntentType.VENDOR:
        parsed_data = VendorData(**data)
    elif intent == IntentType.UNKNOWN:
        parsed_data = UnknownData()
    else:
        parsed_data = UnknownData()
        intent = IntentType.UNKNOWN
    
    return CaptureResponse(
        intent=intent,
        confidence=result.get("confidence", 0.0),
        data=parsed_data,
        missing_fields=missing_fields,
        needs_confirmation=needs_confirmation,
        log_id=log_id,
    )


@router.post("/confirm", response_model=ConfirmResponse)
async def confirm_extraction(
    event_id: str,
    request: ConfirmRequest,
    db: AsyncSession = Depends(get_db),
    extraction_service: ExtractionService = Depends(get_extraction_service),
) -> ConfirmResponse:
    """
    Confirm and persist extracted data.
    
    After reviewing the extracted data from /extract, the user can confirm
    to save it to the appropriate table in the database.
    
    Cannot confirm 'unknown' intent - user must provide clarification first.
    """
    await get_event_or_404(event_id, db)
    
    if request.intent == IntentType.UNKNOWN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot confirm unknown intent. Please clarify the input.",
        )
    
    data_dict = request.data.model_dump()
    
    success, message, created_id = await extraction_service.confirm_and_persist(
        log_id=request.log_id,
        event_id=event_id,
        intent=request.intent,
        data=data_dict,
        db=db,
    )
    
    return ConfirmResponse(
        success=success,
        message=message,
        created_id=created_id,
    )


@router.post("/reject", response_model=ConfirmResponse)
async def reject_extraction(
    event_id: str,
    log_id: str,
    db: AsyncSession = Depends(get_db),
    extraction_service: ExtractionService = Depends(get_extraction_service),
) -> ConfirmResponse:
    """
    Reject an extraction.
    
    If the extracted data is incorrect, the user can reject it.
    This updates the AI log status for debugging purposes.
    """
    await get_event_or_404(event_id, db)
    
    success = await extraction_service.reject(log_id, db)
    
    if success:
        return ConfirmResponse(
            success=True,
            message="Extraction rejected",
            created_id=None,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI log not found",
        )
