"""Prometheus 文本 + Dashboard JSON 聚合。"""
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Response
from sqlalchemy import case, func, select

from app.api.schemas import MetricsSummary, ProviderByStat, TrendPoint
from app.core import metrics
from app.core.db import session_scope
from app.models.notification import Notification, NotificationStatus

router = APIRouter(tags=["meta"])

_HOUR_FMT = "%Y-%m-%dT%H:00:00Z"
_TREND_HOURS = 24


@router.get("/metrics")
def get_metrics() -> Response:
    return Response(content=metrics.render_all(), media_type="text/plain; version=0.0.4")


@router.get("/v1/metrics/summary", response_model=MetricsSummary)
def metrics_summary() -> MetricsSummary:
    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    since_24h = now - timedelta(hours=_TREND_HOURS - 1)

    succeeded = NotificationStatus.SUCCEEDED.value
    dead = NotificationStatus.DEAD_LETTER.value
    inflight_states = (NotificationStatus.PENDING.value, NotificationStatus.IN_FLIGHT.value)

    succ_case = case((Notification.status == succeeded, 1), else_=0)
    fail_case = case((Notification.status == dead, 1), else_=0)
    inflight_case = case((Notification.status.in_(inflight_states), 1), else_=0)

    with session_scope() as s:
        # 全表的 inflight / dlq_total（不限 24h）。
        inflight = s.execute(
            select(func.count())
            .select_from(Notification)
            .where(Notification.status.in_(inflight_states))
        ).scalar_one()
        dlq_total = s.execute(
            select(func.count())
            .select_from(Notification)
            .where(Notification.status == dead)
        ).scalar_one()

        # 24h 成功率：SUCCEEDED / (SUCCEEDED + DEAD_LETTER)。
        sr_row = s.execute(
            select(func.sum(succ_case), func.sum(fail_case))
            .where(Notification.created_at >= since_24h)
        ).one()
        ok = int(sr_row[0] or 0)
        bad = int(sr_row[1] or 0)
        success_rate = (ok / (ok + bad)) if (ok + bad) > 0 else 1.0

        # 24h trend：按小时分桶。
        bucket_col = func.strftime(_HOUR_FMT, Notification.created_at).label("bucket")
        trend_rows = s.execute(
            select(
                bucket_col,
                func.sum(succ_case).label("ok"),
                func.sum(fail_case).label("bad"),
                func.sum(inflight_case).label("inflight"),
            )
            .where(Notification.created_at >= since_24h)
            .group_by(bucket_col)
        ).all()

        # by_provider：所有时间维度的 status 计数。
        bp_rows = s.execute(
            select(Notification.provider, Notification.status, func.count())
            .group_by(Notification.provider, Notification.status)
        ).all()

    by_bucket = {row.bucket: (int(row.ok or 0), int(row.bad or 0), int(row.inflight or 0))
                 for row in trend_rows}
    trend: list[TrendPoint] = []
    for i in range(_TREND_HOURS):
        ts = since_24h + timedelta(hours=i)
        key = ts.strftime(_HOUR_FMT)
        ok_, bad_, inf_ = by_bucket.get(key, (0, 0, 0))
        trend.append(TrendPoint(t=key, succeeded=ok_, failed=bad_, inflight=inf_))

    by_provider_map: dict[str, dict[str, int]] = {}
    for provider, status, cnt in bp_rows:
        by_provider_map.setdefault(provider, {})[status] = cnt
    by_provider = [
        ProviderByStat(
            provider=p,
            succeeded=stats.get(succeeded, 0),
            failed=stats.get(dead, 0),
            dlq=stats.get(dead, 0),
        )
        for p, stats in sorted(by_provider_map.items())
    ]

    p95_seconds = metrics.estimate_percentile_seconds(
        metrics.notification_delivery_duration_seconds, 0.95
    )
    p95_ms = round((p95_seconds or 0.0) * 1000.0, 2)

    return MetricsSummary(
        success_rate=round(success_rate, 4),
        inflight=int(inflight),
        dlq_total=int(dlq_total),
        p95_latency_ms=p95_ms,
        trend=trend,
        by_provider=by_provider,
    )
