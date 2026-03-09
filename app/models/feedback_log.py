import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Text, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.event import Event
    from app.models.ai_log import AILog


class FeedbackLog(Base):
    """User feedback log for LLM self-improvement tracking."""
    
    __tablename__ = "feedback_logs"
    
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    event_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=True,
    )
    ai_log_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("ai_logs.id", ondelete="SET NULL"),
        nullable=True,
    )
    user_feedback: Mapped[str] = mapped_column(Text, nullable=False)
    conversation_history: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_user_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_llm_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    
    event: Mapped[Optional["Event"]] = relationship("Event")
    ai_log: Mapped[Optional["AILog"]] = relationship("AILog")
