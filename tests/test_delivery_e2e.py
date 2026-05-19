"""端到端：用 respx mock 外部供应商，驱动 worker.run_once 验证全链路。"""
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx

from app.core.db import session_scope
from app.delivery.worker import DeliveryWorker
from app.models.notification import Notification, NotificationStatus


@pytest.fixture(autouse=True)
def _registry(providers_yaml):  # noqa: ARG001  fixture 触发 monkeypatch + reset_registry
    return providers_yaml


def _insert(provider: str, payload: dict, *, key: str, due_in: int = -1) -> str:
    """造一条 PENDING 单。due_in 负数表示已经到期。"""
    import uuid

    nid = f"ntf_{uuid.uuid4().hex[:12]}"
    now = datetime.now(UTC)
    with session_scope() as s:
        s.add(
            Notification(
                id=nid,
                idempotency_key=key,
                provider=provider,
                payload=payload,
                status=NotificationStatus.PENDING,
                attempts=0,
                next_retry_at=now + timedelta(seconds=due_in),
                created_at=now,
            )
        )
    return nid


def _read(nid: str) -> Notification:
    with session_scope() as s:
        ntf = s.get(Notification, nid)
        assert ntf is not None
        s.refresh(ntf)
        return ntf


@pytest.mark.asyncio
async def test_2xx_marks_succeeded():
    nid = _insert("demo-crm", {"user_id": 1, "event": "x"}, key="k1")
    with respx.mock(assert_all_called=True) as router:
        router.post("https://crm.example.com/api/contacts").respond(200, json={"ok": True})
        w = DeliveryWorker()
        w._http_client = httpx.AsyncClient()
        await w.run_once()
        await w._http_client.aclose()
    ntf = _read(nid)
    assert ntf.status == NotificationStatus.SUCCEEDED
    assert ntf.attempts == 1
    assert ntf.delivered_at is not None


@pytest.mark.asyncio
async def test_4xx_immediately_dead_letters():
    nid = _insert("demo-crm", {"user_id": 1, "event": "x"}, key="k2")
    with respx.mock() as router:
        router.post("https://crm.example.com/api/contacts").respond(400, json={"err": "bad"})
        w = DeliveryWorker()
        w._http_client = httpx.AsyncClient()
        await w.run_once()
        await w._http_client.aclose()
    ntf = _read(nid)
    assert ntf.status == NotificationStatus.DEAD_LETTER
    assert ntf.attempts == 1
    assert "client_error_400" in ntf.last_error


@pytest.mark.asyncio
async def test_5xx_reschedules_with_backoff():
    nid = _insert("demo-crm", {"user_id": 1, "event": "x"}, key="k3")
    with respx.mock() as router:
        router.post("https://crm.example.com/api/contacts").respond(503)
        w = DeliveryWorker()
        w._http_client = httpx.AsyncClient()
        await w.run_once()
        await w._http_client.aclose()
    ntf = _read(nid)
    assert ntf.status == NotificationStatus.PENDING
    assert ntf.attempts == 1
    # 退避至少 0.8s（1s × (1-20%)）
    delta = (ntf.next_retry_at - datetime.now(UTC)).total_seconds()
    assert delta > 0


@pytest.mark.asyncio
async def test_template_render_error_dead_letters():
    """payload 缺字段（must_exist），demo-strict 模板渲染必失败。"""
    nid = _insert("demo-strict", {"other": "x"}, key="k4")
    w = DeliveryWorker()
    w._http_client = httpx.AsyncClient()
    await w.run_once()
    await w._http_client.aclose()
    ntf = _read(nid)
    assert ntf.status == NotificationStatus.DEAD_LETTER
    assert "template_error" in (ntf.last_error or "")


@pytest.mark.asyncio
async def test_breaker_skips_dispatch_after_consecutive_failures():
    """连续 5 次失败 → 熔断 → 新单不被派发但仍 PENDING。"""
    from app.core.config import get_settings
    from app.delivery.breaker import BreakerState, get_breaker

    s = get_settings()
    threshold = s.breaker_fail_threshold
    breaker = get_breaker()

    # 模拟连续失败把熔断器打开
    for _ in range(threshold):
        breaker.record_failure("demo-crm")
    assert breaker.state_of("demo-crm") == BreakerState.OPEN

    nid = _insert("demo-crm", {"user_id": 1, "event": "x"}, key="bk-1")
    w = DeliveryWorker()
    w._http_client = httpx.AsyncClient()
    dispatched = await w.run_once()
    await w._http_client.aclose()

    assert dispatched == 0
    ntf = _read(nid)
    assert ntf.status == NotificationStatus.PENDING  # 仍在排队等熔断恢复


@pytest.mark.asyncio
async def test_5xx_then_2xx_eventually_succeeds():
    """先 503 → 重试调度 → 再 200 → SUCCEEDED。"""
    nid = _insert("demo-crm", {"user_id": 1, "event": "x"}, key="k-recovery")

    with respx.mock() as router:
        route = router.post("https://crm.example.com/api/contacts")
        route.side_effect = [
            httpx.Response(503),
            httpx.Response(200),
        ]

        w = DeliveryWorker()
        w._http_client = httpx.AsyncClient()
        # 第一次：503
        await w.run_once()
        ntf = _read(nid)
        assert ntf.status == NotificationStatus.PENDING

        # 把 next_retry_at 拉到过去，模拟时间流逝
        with session_scope() as s:
            ntf2 = s.get(Notification, nid)
            ntf2.next_retry_at = datetime.now(UTC) - timedelta(seconds=1)

        # 第二次：200
        await w.run_once()
        await w._http_client.aclose()

    ntf = _read(nid)
    assert ntf.status == NotificationStatus.SUCCEEDED
    assert ntf.attempts == 2
