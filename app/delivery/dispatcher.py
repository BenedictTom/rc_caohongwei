"""核心投递函数：渲染 → HTTP 调用 → 分类 → 推进状态机。

设计要点：
- dispatch() 只走一条线性叙事（加载、渲染、发送、决策、持久化），不在分支里散落副作用
- 终态决策（_decide_terminal）和终态应用（_apply_outcome）解耦——前者纯函数，后者集中副作用
"""
import time
from datetime import UTC, datetime
from enum import StrEnum

import httpx
import structlog

from app.core import metrics
from app.core.config import get_settings
from app.core.db import session_scope
from app.core.providers import get_registry
from app.delivery.backoff import compute_next_retry_at
from app.delivery.breaker import BreakerState, get_breaker
from app.delivery.classifier import (
    ClassifiedResult,
    Outcome,
    classify_exception,
    classify_response,
)
from app.delivery.renderer import RenderedRequest, TemplateRenderError, render
from app.models.notification import Notification, NotificationStatus

log = structlog.get_logger("dispatcher")


_BREAKER_STATE_NUM = {
    BreakerState.CLOSED: 0,
    BreakerState.HALF_OPEN: 1,
    BreakerState.OPEN: 2,
}


class TerminalOutcome(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    DEAD_LETTER = "DEAD_LETTER"
    RETRY = "RETRY"


async def dispatch(notification_id: str, *, http_client: httpx.AsyncClient) -> None:
    """投递单条通知。所有状态变更都写回 DB。"""
    snapshot = _claim_snapshot(notification_id)
    if snapshot is None:
        return
    provider_name, payload, attempts_after = snapshot

    provider = get_registry().get(provider_name)
    if provider is None:
        _apply_outcome(
            notification_id, attempts_after, provider_name,
            TerminalOutcome.DEAD_LETTER,
            reason=f"unknown_provider:{provider_name}",
            response_summary=None,
        )
        return

    try:
        req = render(provider, payload)
    except TemplateRenderError as e:
        log.error(
            "template_render_failed",
            id=notification_id, provider=provider_name, error=str(e),
        )
        _apply_outcome(
            notification_id, attempts_after, provider_name,
            TerminalOutcome.DEAD_LETTER,
            reason=f"template_error:{e}",
            response_summary=None,
        )
        return

    result, elapsed = await _do_http(http_client, req)
    metrics.notification_delivery_duration_seconds.observe(elapsed, provider=provider_name)

    final = _decide_terminal(result, attempts_after, get_settings().max_retry_attempts)
    log.info(
        "delivery_attempt",
        id=notification_id,
        provider=provider_name,
        attempt=attempts_after,
        outcome=final,
        reason=result.reason,
        elapsed_ms=int(elapsed * 1000),
    )
    _apply_outcome(
        notification_id, attempts_after, provider_name, final,
        reason=result.reason if final != TerminalOutcome.SUCCEEDED else "ok",
        response_summary=result.response_summary,
        retry_minimum_seconds=result.minimum_retry_seconds,
    )


def _decide_terminal(
    result: ClassifiedResult, attempts_after: int, max_attempts: int
) -> TerminalOutcome:
    """纯函数：根据分类结果与已尝试次数判定终态。便于单测。"""
    if result.outcome == Outcome.SUCCESS:
        return TerminalOutcome.SUCCEEDED
    if result.outcome == Outcome.DEAD_LETTER:
        return TerminalOutcome.DEAD_LETTER
    # RETRY：但若已达上限，转 DLQ
    if attempts_after >= max_attempts:
        return TerminalOutcome.DEAD_LETTER
    return TerminalOutcome.RETRY


def _apply_outcome(
    notification_id: str,
    attempts: int,
    provider_name: str,
    final: TerminalOutcome,
    *,
    reason: str,
    response_summary: str | None,
    retry_minimum_seconds: int = 0,
) -> None:
    """集中应用终态：DB 状态 + 熔断器 + 指标。"""
    breaker = get_breaker()
    if final == TerminalOutcome.SUCCEEDED:
        breaker.record_success(provider_name)
        _persist_success(notification_id, attempts, response_summary)
    elif final == TerminalOutcome.DEAD_LETTER:
        breaker.record_failure(provider_name)
        _persist_dead_letter(notification_id, attempts, reason, response_summary)
        metrics.notifications_dlq_total.inc(provider=provider_name)
    else:  # RETRY
        breaker.record_failure(provider_name)
        next_at = compute_next_retry_at(
            attempts, now=datetime.now(UTC), minimum_seconds=retry_minimum_seconds
        )
        _persist_retry(notification_id, attempts, next_at, reason, response_summary)

    metrics.circuit_breaker_state.set(
        _BREAKER_STATE_NUM[breaker.state_of(provider_name)], provider=provider_name
    )
    metrics.notifications_delivered_total.inc(provider=provider_name, status=final)


def _claim_snapshot(notification_id: str) -> tuple[str, dict, int] | None:
    """读取 IN_FLIGHT 状态下的工作单元快照。返回 (provider, payload, attempts_after)。"""
    with session_scope() as s:
        ntf = s.get(Notification, notification_id)
        if ntf is None:
            log.warning("notification_missing", id=notification_id)
            return None
        if ntf.status != NotificationStatus.IN_FLIGHT:
            log.warning(
                "notification_not_in_flight", id=notification_id, status=ntf.status
            )
            return None
        return ntf.provider, dict(ntf.payload), ntf.attempts + 1


async def _do_http(
    client: httpx.AsyncClient, req: RenderedRequest
) -> tuple[ClassifiedResult, float]:
    timeout = httpx.Timeout(req.timeout_ms / 1000.0)
    started = time.perf_counter()
    try:
        resp = await client.request(
            method=req.method,
            url=req.url,
            headers=req.headers,
            content=req.body,
            timeout=timeout,
        )
    except Exception as e:
        return classify_exception(e), time.perf_counter() - started
    return classify_response(resp), time.perf_counter() - started


def _persist_success(
    notification_id: str, attempts: int, response_summary: str | None
) -> None:
    with session_scope() as s:
        ntf = s.get(Notification, notification_id)
        if ntf is None:
            return
        ntf.status = NotificationStatus.SUCCEEDED
        ntf.attempts = attempts
        ntf.last_error = None
        ntf.last_response_summary = response_summary
        ntf.delivered_at = datetime.now(UTC)


def _persist_dead_letter(
    notification_id: str,
    attempts: int,
    reason: str,
    response_summary: str | None,
) -> None:
    with session_scope() as s:
        ntf = s.get(Notification, notification_id)
        if ntf is None:
            return
        ntf.status = NotificationStatus.DEAD_LETTER
        ntf.attempts = attempts
        ntf.last_error = reason[:500]
        ntf.last_response_summary = response_summary


def _persist_retry(
    notification_id: str,
    attempts: int,
    next_at: datetime,
    reason: str,
    response_summary: str | None,
) -> None:
    with session_scope() as s:
        ntf = s.get(Notification, notification_id)
        if ntf is None:
            return
        ntf.status = NotificationStatus.PENDING
        ntf.attempts = attempts
        ntf.next_retry_at = next_at
        ntf.last_error = reason[:500]
        ntf.last_response_summary = response_summary
