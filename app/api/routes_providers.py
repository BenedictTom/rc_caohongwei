"""GET /v1/providers：合并配置 + 熔断态 + 24h 成功率序列。"""
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter
from sqlalchemy import case, func, select

from app.api.schemas import ProviderItem, RateSeriesPoint
from app.core.db import session_scope
from app.core.providers import ProviderConfig, get_registry
from app.delivery.breaker import get_breaker
from app.models.notification import Notification, NotificationStatus

router = APIRouter(prefix="/v1", tags=["providers"])

_HOUR_FMT = "%Y-%m-%dT%H:00:00Z"
_HOURS = 24


@router.get("/providers", response_model=list[ProviderItem])
def list_providers() -> list[ProviderItem]:
    registry = get_registry()
    breaker = get_breaker()

    now_hour = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    since_24h = now_hour - timedelta(hours=_HOURS - 1)

    succeeded = NotificationStatus.SUCCEEDED.value
    dead = NotificationStatus.DEAD_LETTER.value
    succ_case = case((Notification.status == succeeded, 1), else_=0)
    fail_case = case((Notification.status == dead, 1), else_=0)

    bucket_col = func.strftime(_HOUR_FMT, Notification.created_at).label("bucket")
    with session_scope() as s:
        rows = s.execute(
            select(
                Notification.provider,
                bucket_col,
                func.sum(succ_case).label("ok"),
                func.sum(fail_case).label("bad"),
            )
            .where(Notification.created_at >= since_24h)
            .where(Notification.status.in_((succeeded, dead)))
            .group_by(Notification.provider, bucket_col)
        ).all()

    series_map: dict[tuple[str, str], tuple[int, int]] = {
        (row.provider, row.bucket): (int(row.ok or 0), int(row.bad or 0)) for row in rows
    }

    items: list[ProviderItem] = []
    for cfg in registry.providers.values():
        items.append(_build_item(cfg, breaker, series_map, since_24h))
    return items


def _build_item(
    cfg: ProviderConfig,
    breaker,
    series_map: dict[tuple[str, str], tuple[int, int]],
    since_24h: datetime,
) -> ProviderItem:
    state, cooldown = breaker.state_with_cooldown(cfg.name)
    series: list[RateSeriesPoint] = []
    for i in range(_HOURS):
        ts = since_24h + timedelta(hours=i)
        key = ts.strftime(_HOUR_FMT)
        ok, bad = series_map.get((cfg.name, key), (0, 0))
        rate = (ok / (ok + bad)) if (ok + bad) > 0 else 1.0
        series.append(RateSeriesPoint(t=key, rate=round(rate, 4)))

    return ProviderItem(
        name=cfg.name,
        url=cfg.url,
        method=cfg.method,
        auth_type=cfg.auth.type,
        auth_hint=cfg.auth.token_env,
        timeout_ms=cfg.timeout_ms,
        headers=cfg.headers,
        body_template=cfg.body_template,
        breaker=state.value,
        breaker_cooldown_seconds=cooldown,
        success_rate_series=series,
    )
