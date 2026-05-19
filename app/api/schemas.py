"""对外 JSON 一律 camelCase；内部字段名仍保持 PEP 8 的 snake_case。

约定：所有响应/请求模型继承 `CamelModel`，由 `alias_generator=to_camel`
统一处理双向转换；`populate_by_name=True` 让 FastAPI 以字段名实例化时不报错。
"""
from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


T = TypeVar("T")


class Page(CamelModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


# ---------- intake ----------

class NotificationCreateRequest(CamelModel):
    provider: str = Field(min_length=1, max_length=64)
    payload: dict[str, Any]


class NotificationCreateResponse(CamelModel):
    id: str
    status: str
    duplicated: bool


# ---------- list / detail ----------

class NotificationItem(CamelModel):
    id: str
    idempotency_key: str
    provider: str
    status: str
    attempts: int
    payload: dict[str, Any]
    created_at: datetime
    delivered_at: datetime | None = None
    next_retry_at: datetime | None = None
    last_error: str | None = None
    last_response_summary: str | None = None


# ---------- meta ----------

class HealthResponse(CamelModel):
    status: str
    db: str
    scheduler: str
    failed: list[str] = []


# ---------- dashboard ----------

class TrendPoint(CamelModel):
    t: str
    succeeded: int
    failed: int
    inflight: int


class ProviderByStat(CamelModel):
    provider: str
    succeeded: int
    failed: int
    dlq: int


class MetricsSummary(CamelModel):
    success_rate: float
    inflight: int
    dlq_total: int
    p95_latency_ms: float
    trend: list[TrendPoint]
    by_provider: list[ProviderByStat]


# ---------- providers ----------

class RateSeriesPoint(CamelModel):
    t: str
    rate: float


class ProviderItem(CamelModel):
    name: str
    url: str
    method: str
    auth_type: str
    auth_hint: str | None = None
    timeout_ms: int
    headers: dict[str, str]
    body_template: str
    breaker: str
    breaker_cooldown_seconds: int | None = None
    success_rate_series: list[RateSeriesPoint]
