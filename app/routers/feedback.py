from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.feedback_log import FeedbackLog

router = APIRouter()


class FeedbackCreate(BaseModel):
    """Schema for creating feedback."""
    event_id: Optional[str] = None
    ai_log_id: Optional[str] = None
    user_feedback: str
    conversation_history: Optional[str] = None
    last_user_message: Optional[str] = None
    last_llm_response: Optional[str] = None


class FeedbackResponse(BaseModel):
    """Schema for feedback response."""
    id: str
    event_id: Optional[str]
    user_feedback: str
    is_resolved: bool
    created_at: str


@router.post("", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    feedback_data: FeedbackCreate,
    db: AsyncSession = Depends(get_db),
) -> FeedbackResponse:
    """Submit user feedback about LLM performance."""
    feedback = FeedbackLog(
        event_id=feedback_data.event_id,
        ai_log_id=feedback_data.ai_log_id,
        user_feedback=feedback_data.user_feedback,
        conversation_history=feedback_data.conversation_history,
        last_user_message=feedback_data.last_user_message,
        last_llm_response=feedback_data.last_llm_response,
    )
    db.add(feedback)
    await db.commit()
    await db.refresh(feedback)
    
    return FeedbackResponse(
        id=feedback.id,
        event_id=feedback.event_id,
        user_feedback=feedback.user_feedback,
        is_resolved=feedback.is_resolved,
        created_at=feedback.created_at.isoformat(),
    )


@router.get("", response_model=List[FeedbackResponse])
async def list_feedback(
    resolved: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
) -> List[FeedbackResponse]:
    """List all feedback logs (for development triage)."""
    query = select(FeedbackLog).order_by(FeedbackLog.created_at.desc())
    
    if resolved is not None:
        query = query.where(FeedbackLog.is_resolved == resolved)
    
    result = await db.execute(query)
    feedbacks = result.scalars().all()
    
    return [
        FeedbackResponse(
            id=f.id,
            event_id=f.event_id,
            user_feedback=f.user_feedback,
            is_resolved=f.is_resolved,
            created_at=f.created_at.isoformat(),
        )
        for f in feedbacks
    ]


@router.get("/{feedback_id}")
async def get_feedback_detail(
    feedback_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get detailed feedback log including conversation history."""
    result = await db.execute(
        select(FeedbackLog).where(FeedbackLog.id == feedback_id)
    )
    feedback = result.scalar_one_or_none()
    
    if not feedback:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feedback not found",
        )
    
    return {
        "id": feedback.id,
        "event_id": feedback.event_id,
        "ai_log_id": feedback.ai_log_id,
        "user_feedback": feedback.user_feedback,
        "conversation_history": feedback.conversation_history,
        "last_user_message": feedback.last_user_message,
        "last_llm_response": feedback.last_llm_response,
        "is_resolved": feedback.is_resolved,
        "resolution_notes": feedback.resolution_notes,
        "created_at": feedback.created_at.isoformat(),
    }


@router.patch("/{feedback_id}/resolve")
async def resolve_feedback(
    feedback_id: str,
    resolution_notes: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Mark feedback as resolved with optional notes."""
    result = await db.execute(
        select(FeedbackLog).where(FeedbackLog.id == feedback_id)
    )
    feedback = result.scalar_one_or_none()
    
    if not feedback:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feedback not found",
        )
    
    feedback.is_resolved = True
    if resolution_notes:
        feedback.resolution_notes = resolution_notes
    
    await db.commit()
    
    return {"success": True, "message": "Feedback marked as resolved"}
