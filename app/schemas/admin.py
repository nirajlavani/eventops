from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class DailyMetrics(BaseModel):
    date: str
    llm_calls: int = 0
    rag_queries: int = 0
    embeddings: int = 0
    extractions: int = 0
    total_tokens: int = 0
    avg_latency_ms: float = 0
    errors: int = 0


class IntentBreakdown(BaseModel):
    intent: str
    count: int
    pct: float


class LatencyByType(BaseModel):
    extraction_ms: Optional[float] = None
    rag_query_ms: Optional[float] = None
    embedding_ms: Optional[float] = None


class ModelTierInfo(BaseModel):
    tier: str
    model: str
    purpose: str

class MetricsSummary(BaseModel):
    primary_model: Optional[str] = None
    models_used: dict[str, int] = {}
    model_tiers: list[ModelTierInfo] = []
    total_llm_calls: int
    total_tokens: int
    estimated_cost_usd: float
    avg_latency_ms: float
    latency_by_type: LatencyByType
    error_rate: float
    total_rag_queries: int
    avg_rag_score: Optional[float]
    avg_rag_chunks_returned: Optional[float]
    intent_breakdown: list[IntentBreakdown]
    daily: list[DailyMetrics]
    extraction_statuses: dict[str, int]


class RecentMetric(BaseModel):
    id: str
    metric_type: str
    model_name: Optional[str]
    prompt_tokens: Optional[int]
    completion_tokens: Optional[int]
    total_tokens: Optional[int]
    latency_ms: Optional[int]
    intent: Optional[str]
    confidence: Optional[float]
    status: Optional[str]
    rag_top_score: Optional[float]
    rag_chunks_returned: Optional[int]
    created_at: datetime


class HealthStatus(BaseModel):
    error_rate_1h: float
    p50_latency_ms: Optional[float]
    p95_latency_ms: Optional[float]
    last_success_at: Optional[datetime]
    total_calls_1h: int
