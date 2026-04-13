import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import select, func, case, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import Settings
from app.database import get_db
from app.models.ai_metric import AIMetric, MetricType
from app.models.ai_log import AILog, AILogStatus
from app.models.attachment import Attachment
from app.models.vendor import Vendor
from app.schemas.admin import (
    MetricsSummary,
    LatencyByType,
    DailyMetrics,
    IntentBreakdown,
    RecentMetric,
    HealthStatus,
)

logger = logging.getLogger(__name__)
router = APIRouter()

COST_PER_1K_TOKENS = 0.0002


@router.get("/metrics/summary", response_model=MetricsSummary)
async def metrics_summary(
    days: int = Query(7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
) -> MetricsSummary:
    since = datetime.utcnow() - timedelta(days=days)

    rows = (await db.execute(
        select(AIMetric).where(AIMetric.created_at >= since)
    )).scalars().all()

    total_calls = len(rows)
    total_tokens = sum(r.total_tokens or 0 for r in rows)
    latencies = [r.latency_ms for r in rows if r.latency_ms is not None]
    avg_latency = sum(latencies) / len(latencies) if latencies else 0
    errors = sum(1 for r in rows if r.status == "error")
    error_rate = errors / total_calls if total_calls else 0

    def _avg_latency_for(metric_type):
        vals = [r.latency_ms for r in rows if r.metric_type == metric_type and r.latency_ms is not None]
        return round(sum(vals) / len(vals), 1) if vals else None

    latency_by_type = LatencyByType(
        extraction_ms=_avg_latency_for(MetricType.EXTRACTION),
        rag_query_ms=_avg_latency_for(MetricType.RAG_QUERY),
        embedding_ms=_avg_latency_for(MetricType.EMBEDDING),
    )

    rag_rows = [r for r in rows if r.metric_type == MetricType.RAG_QUERY]
    rag_scores = [r.rag_top_score for r in rag_rows if r.rag_top_score is not None]
    rag_chunks = [r.rag_chunks_returned for r in rag_rows if r.rag_chunks_returned is not None]

    intent_counts: dict[str, int] = {}
    for r in rows:
        if r.intent:
            intent_counts[r.intent] = intent_counts.get(r.intent, 0) + 1
    intent_total = sum(intent_counts.values()) or 1
    intent_breakdown = [
        IntentBreakdown(intent=k, count=v, pct=round(v / intent_total * 100, 1))
        for k, v in sorted(intent_counts.items(), key=lambda x: -x[1])
    ]

    day_buckets: dict[str, dict] = {}
    for r in rows:
        day_key = r.created_at.strftime("%Y-%m-%d")
        if day_key not in day_buckets:
            day_buckets[day_key] = {
                "llm_calls": 0, "rag_queries": 0, "embeddings": 0,
                "extractions": 0, "total_tokens": 0, "latency_sum": 0,
                "latency_count": 0, "errors": 0,
            }
        b = day_buckets[day_key]
        if r.metric_type == MetricType.LLM_CALL:
            b["llm_calls"] += 1
        elif r.metric_type == MetricType.RAG_QUERY:
            b["rag_queries"] += 1
        elif r.metric_type == MetricType.EMBEDDING:
            b["embeddings"] += 1
        elif r.metric_type == MetricType.EXTRACTION:
            b["extractions"] += 1
        b["total_tokens"] += r.total_tokens or 0
        if r.latency_ms is not None:
            b["latency_sum"] += r.latency_ms
            b["latency_count"] += 1
        if r.status == "error":
            b["errors"] += 1

    daily = []
    for day_key in sorted(day_buckets):
        b = day_buckets[day_key]
        daily.append(DailyMetrics(
            date=day_key,
            llm_calls=b["llm_calls"],
            rag_queries=b["rag_queries"],
            embeddings=b["embeddings"],
            extractions=b["extractions"],
            total_tokens=b["total_tokens"],
            avg_latency_ms=round(b["latency_sum"] / b["latency_count"], 1) if b["latency_count"] else 0,
            errors=b["errors"],
        ))

    log_rows = (await db.execute(
        select(AILog.status, func.count(AILog.id))
        .where(AILog.created_at >= since)
        .group_by(AILog.status)
    )).all()
    extraction_statuses = {s.value if hasattr(s, 'value') else str(s): c for s, c in log_rows}

    model_counts: dict[str, int] = {}
    for r in rows:
        if r.model_name:
            model_counts[r.model_name] = model_counts.get(r.model_name, 0) + 1
    primary_model = max(model_counts, key=model_counts.get) if model_counts else Settings().llm_model

    return MetricsSummary(
        primary_model=primary_model,
        models_used=model_counts,
        total_llm_calls=total_calls,
        total_tokens=total_tokens,
        estimated_cost_usd=round(total_tokens / 1000 * COST_PER_1K_TOKENS, 4),
        avg_latency_ms=round(avg_latency, 1),
        latency_by_type=latency_by_type,
        error_rate=round(error_rate, 4),
        total_rag_queries=len(rag_rows),
        avg_rag_score=round(sum(rag_scores) / len(rag_scores), 3) if rag_scores else None,
        avg_rag_chunks_returned=round(sum(rag_chunks) / len(rag_chunks), 1) if rag_chunks else None,
        intent_breakdown=intent_breakdown,
        daily=daily,
        extraction_statuses=extraction_statuses,
    )


@router.get("/metrics/recent", response_model=list[RecentMetric])
async def metrics_recent(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[RecentMetric]:
    rows = (await db.execute(
        select(AIMetric)
        .order_by(desc(AIMetric.created_at))
        .offset(offset)
        .limit(limit)
    )).scalars().all()

    return [
        RecentMetric(
            id=r.id,
            metric_type=r.metric_type.value,
            model_name=r.model_name,
            prompt_tokens=r.prompt_tokens,
            completion_tokens=r.completion_tokens,
            total_tokens=r.total_tokens,
            latency_ms=r.latency_ms,
            intent=r.intent,
            confidence=r.confidence,
            status=r.status,
            rag_top_score=r.rag_top_score,
            rag_chunks_returned=r.rag_chunks_returned,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.get("/metrics/health", response_model=HealthStatus)
async def metrics_health(
    db: AsyncSession = Depends(get_db),
) -> HealthStatus:
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)

    rows = (await db.execute(
        select(AIMetric).where(AIMetric.created_at >= one_hour_ago)
    )).scalars().all()

    total = len(rows)
    errors = sum(1 for r in rows if r.status == "error")
    latencies = sorted(r.latency_ms for r in rows if r.latency_ms is not None)

    p50 = latencies[len(latencies) // 2] if latencies else None
    p95_idx = int(len(latencies) * 0.95)
    p95 = latencies[min(p95_idx, len(latencies) - 1)] if latencies else None

    success_rows = [r for r in rows if r.status == "success"]
    last_success = max((r.created_at for r in success_rows), default=None) if success_rows else None

    return HealthStatus(
        error_rate_1h=round(errors / total, 4) if total else 0,
        p50_latency_ms=p50,
        p95_latency_ms=p95,
        last_success_at=last_success,
        total_calls_1h=total,
    )


_reindex_status: dict = {"running": False, "total": 0, "done": 0, "errors": []}


@router.post("/reindex")
async def reindex_all_pdfs(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Re-index all PDF attachments across all events with the latest extraction pipeline."""
    if _reindex_status["running"]:
        return JSONResponse(
            {"status": "already_running", **_reindex_status},
            status_code=409,
        )

    result = await db.execute(
        select(Attachment)
        .options(selectinload(Attachment.vendor))
        .where(Attachment.original_filename.ilike("%.pdf"))
    )
    pdfs = list(result.scalars().all())

    if not pdfs:
        return JSONResponse({"status": "no_pdfs", "total": 0})

    _reindex_status.update(running=True, total=len(pdfs), done=0, errors=[])
    pdf_info = [
        {
            "event_id": a.event_id,
            "attachment_id": a.id,
            "file_path": a.file_path,
            "original_filename": a.original_filename,
            "vendor_name": a.vendor.name if a.vendor else None,
        }
        for a in pdfs
    ]

    background_tasks.add_task(_run_reindex, pdf_info)
    return JSONResponse({"status": "started", "total": len(pdfs)})


@router.get("/reindex/status")
async def reindex_status() -> JSONResponse:
    return JSONResponse(_reindex_status)


async def _run_reindex(pdf_info: list[dict]) -> None:
    from app.retrieval.rag_service import RAGService
    rag = RAGService()

    for info in pdf_info:
        file_path = info["file_path"]
        doc_name = info["original_filename"]
        try:
            if not Path(file_path).exists():
                logger.warning("Skipping %s — file not found on disk", doc_name)
                _reindex_status["errors"].append(f"{doc_name}: file missing")
                _reindex_status["done"] += 1
                continue

            rag.delete_document(info["event_id"], info["attachment_id"])

            count = await rag.index_document(
                event_id=info["event_id"],
                attachment_id=info["attachment_id"],
                file_path=file_path,
                document_name=doc_name,
                vendor_name=info["vendor_name"],
            )
            logger.info("Re-indexed %s: %d chunks", doc_name, count)
        except Exception as exc:
            logger.error("Failed to re-index %s: %s", doc_name, exc, exc_info=True)
            _reindex_status["errors"].append(f"{doc_name}: {exc}")
        _reindex_status["done"] += 1

    _reindex_status["running"] = False
    logger.info(
        "Re-index complete: %d/%d succeeded",
        _reindex_status["done"] - len(_reindex_status["errors"]),
        _reindex_status["total"],
    )
