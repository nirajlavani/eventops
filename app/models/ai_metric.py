import uuid
from datetime import datetime
from typing import Optional
from enum import Enum as PyEnum

from sqlalchemy import String, Text, ForeignKey, Enum, Float, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MetricType(str, PyEnum):
    LLM_CALL = "llm_call"
    RAG_QUERY = "rag_query"
    EMBEDDING = "embedding"
    EXTRACTION = "extraction"


class AIMetric(Base):
    """Telemetry row captured per LLM / RAG / embedding operation."""

    __tablename__ = "ai_metrics"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    event_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("events.id", ondelete="CASCADE"), nullable=True
    )
    ai_log_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("ai_logs.id", ondelete="SET NULL"), nullable=True
    )
    metric_type: Mapped[MetricType] = mapped_column(
        Enum(MetricType), nullable=False
    )
    model_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    prompt_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    intent: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    rag_top_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rag_chunks_searched: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    rag_chunks_returned: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
