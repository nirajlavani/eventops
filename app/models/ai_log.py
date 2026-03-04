import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from enum import Enum as PyEnum

from sqlalchemy import String, Text, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.event import Event


class AILogStatus(str, PyEnum):
    """AI log status enumeration."""
    SUCCESS = "success"
    ERROR = "error"
    REJECTED = "rejected"
    PENDING = "pending"


class AILog(Base):
    """AI interaction audit log for debugging and tracking."""
    
    __tablename__ = "ai_logs"
    
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
    user_input: Mapped[str] = mapped_column(Text, nullable=False)
    llm_output: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    status: Mapped[AILogStatus] = mapped_column(
        Enum(AILogStatus),
        default=AILogStatus.PENDING,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    
    event: Mapped[Optional["Event"]] = relationship("Event", back_populates="ai_logs")
