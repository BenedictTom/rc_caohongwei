"""列表查询的公共实现：GET /v1/notifications 与 /v1/dead-letters 共用。"""
from datetime import datetime

from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session

from app.api.schemas import NotificationItem, Page
from app.models.notification import Notification, NotificationStatus


def query_notifications(
    session: Session,
    *,
    status: NotificationStatus | None = None,
    provider: str | None = None,
    q: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = 25,
    offset: int = 0,
) -> Page[NotificationItem]:
    base = select(Notification)
    count_stmt = select(func.count()).select_from(Notification) # pylint: disable=E1102

    if status is not None:
        base = base.where(Notification.status == status)
        count_stmt = count_stmt.where(Notification.status == status)
    if provider:
        base = base.where(Notification.provider == provider)
        count_stmt = count_stmt.where(Notification.provider == provider)
    if since:
        base = base.where(Notification.created_at >= since)
        count_stmt = count_stmt.where(Notification.created_at >= since)
    if until:
        base = base.where(Notification.created_at <= until)
        count_stmt = count_stmt.where(Notification.created_at <= until)
    if q:
        like = f"%{q}%"
        # SQLite JSON 存储为 TEXT，cast 后可走子串匹配；保证三列联合搜索。
        clause = or_(
            Notification.id.like(like),
            Notification.idempotency_key.like(like),
            cast(Notification.payload, String).like(like),
        )
        base = base.where(clause)
        count_stmt = count_stmt.where(clause)

    total = session.execute(count_stmt).scalar_one()

    rows = session.execute(
        base.order_by(Notification.created_at.desc()).offset(offset).limit(limit)
    ).scalars().all()

    items = [NotificationItem.model_validate(r) for r in rows]
    return Page[NotificationItem](items=items, total=total, limit=limit, offset=offset)
