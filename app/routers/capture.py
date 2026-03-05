import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

logger = logging.getLogger(__name__)
from app.models.event import Event
from app.services.extraction import ExtractionService, get_extraction_service
from app.services.context_service import ContextService, get_context_service
from app.schemas.capture import (
    ActionType,
    CaptureRequest,
    CaptureResponse,
    ConfirmRequest,
    ConfirmResponse,
    IntentType,
    PaymentData,
    TaskData,
    CalendarEventData,
    VendorData,
    QueryData,
    QueryResults,
    ConversationData,
    UnknownData,
    ResponseMode,
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
    context_service: ContextService = Depends(get_context_service),
) -> CaptureResponse:
    """
    Extract structured data from natural language text with contextual awareness.
    
    The system retrieves existing payment/vendor records for context,
    allowing the LLM to understand references like "the rest" or "remaining balance".
    
    Response includes:
    - intent: The classified intent type
    - action: "create" for new records, "update" for modifying existing
    - confidence: Model confidence (0.0 - 1.0)
    - data: Extracted structured fields
    - missing_fields: Required fields that couldn't be extracted
    - needs_confirmation: Whether user should review before saving
    - reference_id: ID of existing record to update (if action=update)
    """
    await get_event_or_404(event_id, db)
    
    payment_context = await context_service.get_payment_context(event_id, db)
    context_str = context_service.format_context_for_prompt(payment_context)
    
    logger.info(f"Payment context for event {event_id}: {payment_context}")
    logger.info(f"Formatted context:\n{context_str}")
    
    conversation_history = None
    if request.conversation_history:
        conversation_history = [
            {"role": msg.role, "content": msg.content}
            for msg in request.conversation_history
        ]
    
    result, log_id = await extraction_service.extract(
        user_input=request.text,
        event_id=event_id,
        db=db,
        context=context_str,
        conversation_history=conversation_history,
    )
    
    intent_str = result.get("intent", "unknown")
    try:
        intent = IntentType(intent_str)
    except ValueError:
        intent = IntentType.UNKNOWN
    
    action_str = result.get("action", "create")
    try:
        action = ActionType(action_str)
    except ValueError:
        action = ActionType.CREATE
    
    data = result.get("data", {})
    missing_fields = result.get("missing_fields", [])
    needs_confirmation = result.get("needs_confirmation", True)
    reference_id = result.get("reference_id")
    follow_up_question = result.get("follow_up_question")
    assistant_message = result.get("assistant_message")
    referenced_records = result.get("referenced_records")
    query_results = None
    
    # Map response_mode from result
    response_mode_str = result.get("response_mode", "confirm")
    try:
        response_mode = ResponseMode(response_mode_str)
    except ValueError:
        response_mode = ResponseMode.CONFIRM
    
    if intent == IntentType.PAYMENT:
        parsed_data = PaymentData(**data)
    elif intent == IntentType.TASK:
        parsed_data = TaskData(**data)
    elif intent == IntentType.CALENDAR_EVENT:
        parsed_data = CalendarEventData(**data)
    elif intent == IntentType.VENDOR:
        parsed_data = VendorData(**data)
    elif intent == IntentType.QUERY:
        parsed_data = QueryData(**data)
        query_response = await extraction_service.handle_query(
            event_id=event_id,
            data=data,
            db=db,
        )
        query_results = QueryResults(**query_response)
        needs_confirmation = False
    elif intent == IntentType.CONVERSATION:
        parsed_data = ConversationData(**data) if data else ConversationData()
        needs_confirmation = False
    elif intent == IntentType.UNKNOWN:
        parsed_data = UnknownData()
    else:
        parsed_data = UnknownData()
        intent = IntentType.UNKNOWN
    
    return CaptureResponse(
        intent=intent,
        action=action,
        confidence=result.get("confidence", 0.0),
        data=parsed_data,
        missing_fields=missing_fields,
        needs_confirmation=needs_confirmation,
        reference_id=reference_id,
        follow_up_question=follow_up_question,
        assistant_message=assistant_message,
        response_mode=response_mode,
        referenced_records=referenced_records,
        query_results=query_results,
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
    
    For action="update", the reference_id indicates which record to modify.
    
    Cannot confirm 'unknown' intent - user must provide clarification first.
    """
    await get_event_or_404(event_id, db)
    
    if request.intent == IntentType.UNKNOWN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot confirm unknown intent. Please clarify the input.",
        )
    
    data_dict = request.data.model_dump()
    
    success, message, record_id = await extraction_service.confirm_and_persist(
        log_id=request.log_id,
        event_id=event_id,
        intent=request.intent,
        action=request.action,
        reference_id=request.reference_id,
        data=data_dict,
        db=db,
    )
    
    return ConfirmResponse(
        success=success,
        message=message,
        created_id=record_id,
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
