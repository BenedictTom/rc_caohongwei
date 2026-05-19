"""GET /v1/dead-letters：人工介入查询。共用 NotificationItem + Page 外壳。"""
from datetime import datetime

from fastapi import APIRouter, Query

from app.api._listing import query_notifications
from app.api.schemas import NotificationItem, Page
from app.core.db import session_scope
from app.models.notification import NotificationStatus

router = APIRouter(prefix="/v1", tags=["dlq"])


@router.get("/dead-letters", response_model=Page[NotificationItem])
def list_dead_letters(
    provider: str | None = Query(default=None),
    from_ts: datetime | None = Query(default=None, alias="fromTs"),
    to_ts: datetime | None = Query(default=None, alias="toTs"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> Page[NotificationItem]:
    with session_scope() as s:
        return query_notifications(
            s,
            status=NotificationStatus.DEAD_LETTER,
            provider=provider,
            since=from_ts,
            until=to_ts,
            limit=limit,
            offset=offset,
        )
