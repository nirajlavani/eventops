"""Lightweight helper for recording AI telemetry rows."""

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_metric import AIMetric, MetricType

logger = logging.getLogger(__name__)


async def record_metric(
    db: AsyncSession,
    *,
    metric_type: MetricType,
    event_id: Optional[str] = None,
    ai_log_id: Optional[str] = None,
    model_name: Optional[str] = None,
    prompt_tokens: Optional[int] = None,
    completion_tokens: Optional[int] = None,
    total_tokens: Optional[int] = None,
    latency_ms: Optional[int] = None,
    intent: Optional[str] = None,
    confidence: Optional[float] = None,
    status: Optional[str] = None,
    rag_top_score: Optional[float] = None,
    rag_chunks_searched: Optional[int] = None,
    rag_chunks_returned: Optional[int] = None,
    metadata_json: Optional[str] = None,
) -> None:
    """Write a single metric row. Errors are logged but never propagated."""
    try:
        row = AIMetric(
            metric_type=metric_type,
            event_id=event_id,
            ai_log_id=ai_log_id,
            model_name=model_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            intent=intent,
            confidence=confidence,
            status=status,
            rag_top_score=rag_top_score,
            rag_chunks_searched=rag_chunks_searched,
            rag_chunks_returned=rag_chunks_returned,
            metadata_json=metadata_json,
        )
        db.add(row)
        await db.commit()
    except Exception as exc:
        logger.warning("Failed to write AI metric: %s", exc)
