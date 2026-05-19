"""POST /v1/notifications：收单接口；GET /v1/notifications：列表查询。"""
import hashlib
import json
import uuid
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api._listing import query_notifications
from app.api.schemas import (
    NotificationCreateRequest,
    NotificationCreateResponse,
    NotificationItem,
    Page,
)
from app.core import metrics
from app.core.config import get_settings
from app.core.db import session_scope
from app.core.providers import get_registry
from app.models.notification import Notification, NotificationStatus

router = APIRouter(prefix="/v1", tags=["notifications"])
log = structlog.get_logger("intake")


def _new_id() -> str:
    return f"ntf_{uuid.uuid4().hex[:24]}"


def _payload_size(payload: dict) -> int:
    return len(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def _fallback_idem_key(provider: str, payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(f"{provider}|{canonical}".encode()).hexdigest()
    return f"auto_{digest[:32]}"


@router.post(
    "/notifications",
    response_model=NotificationCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_notification(
    body: NotificationCreateRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> NotificationCreateResponse:
    settings = get_settings()
    registry = get_registry()

    if not registry.has(body.provider):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"unknown provider: {body.provider}",
        )

    size = _payload_size(body.payload)
    if size > settings.payload_max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"payload too large: {size} bytes > {settings.payload_max_bytes}",
        )

    if idempotency_key is None:
        key = _fallback_idem_key(body.provider, body.payload)
        log.warning("idempotency_key_auto_generated", provider=body.provider, generated_key=key)
    else:
        key = idempotency_key

    metrics.notifications_received_total.inc(provider=body.provider)

    # 幂等优先 SELECT：命中直接复用；未命中再 INSERT，由唯一索引兜底竞态
    with session_scope() as s:
        existing = s.execute(
            select(Notification).where(Notification.idempotency_key == key)
        ).scalar_one_or_none()
        if existing is not None:
            log.info(
                "idempotency_hit",
                id=existing.id,
                idempotency_key=key,
                provider=body.provider,
            )
            return NotificationCreateResponse(
                id=existing.id, status=existing.status, duplicated=True
            )

    new_id = _new_id()
    now = datetime.now(UTC)
    try:
        with session_scope() as s:
            s.add(
                Notification(
                    id=new_id,
                    idempotency_key=key,
                    provider=body.provider,
                    payload=body.payload,
                    status=NotificationStatus.PENDING,
                    attempts=0,
                    next_retry_at=now,
                    created_at=now,
                )
            )
    except IntegrityError:
        # 极罕见：两并发请求带同一 key，唯一索引拒绝了我们这一笔
        with session_scope() as s:
            existing = s.execute(
                select(Notification).where(Notification.idempotency_key == key)
            ).scalar_one_or_none()
        if existing is not None:
            return NotificationCreateResponse(
                id=existing.id, status=existing.status, duplicated=True
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="idempotency conflict, retry later",
        ) from None
    except Exception:
        log.exception("intake_db_failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="database unavailable",
        ) from None

    log.info("notification_received", id=new_id, provider=body.provider, idempotency_key=key)
    return NotificationCreateResponse(
        id=new_id, status=NotificationStatus.PENDING, duplicated=False
    )


@router.get("/notifications", response_model=Page[NotificationItem])
def list_notifications(
    status_: NotificationStatus | None = Query(default=None, alias="status"),
    provider: str | None = Query(default=None),
    q: str | None = Query(default=None),
    from_ts: datetime | None = Query(default=None, alias="fromTs"),
    to_ts: datetime | None = Query(default=None, alias="toTs"),
    limit: int = Query(default=25, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> Page[NotificationItem]:
    with session_scope() as s:
        return query_notifications(
            s,
            status=status_,
            provider=provider,
            q=q,
            since=from_ts,
            until=to_ts,
            limit=limit,
            offset=offset,
        )
