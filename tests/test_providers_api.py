"""GET /v1/providers：合并 registry 配置 + 熔断态 + 24h 成功率序列的端到端测试。"""
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import routes_providers
from app.core.db import session_scope
from app.delivery.breaker import get_breaker
from app.models.notification import Notification, NotificationStatus


@pytest.fixture
def app(providers_yaml):  # noqa: ARG001
    app = FastAPI()
    app.include_router(routes_providers.router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


# ---------- 字段映射 ----------

def test_returns_all_providers_in_registry(client):
    body = client.get("/v1/providers").json()
    names = {p["name"] for p in body}
    # conftest 的 providers_yaml fixture 注入这两个 provider
    assert names == {"demo-crm", "demo-strict"}


def test_provider_fields_camelcase_and_complete(client):
    body = client.get("/v1/providers").json()
    crm = next(p for p in body if p["name"] == "demo-crm")
    # camelCase 出口
    assert {
        "name", "url", "method", "authType", "authHint",
        "timeoutMs", "headers", "bodyTemplate",
        "breaker", "breakerCooldownSeconds", "successRateSeries",
    } <= set(crm.keys())
    # snake_case 不应出现
    assert "auth_type" not in crm
    assert "timeout_ms" not in crm

    # 字段值核对（来自 conftest 的 providers_yaml）
    assert crm["url"] == "https://crm.example.com/api/contacts"
    assert crm["method"] == "POST"
    assert crm["authType"] == "bearer"
    assert crm["authHint"] == "CRM_TOKEN"
    assert crm["timeoutMs"] == 1000
    assert crm["headers"] == {"Content-Type": "application/json"}
    assert "{{ payload.user_id }}" in crm["bodyTemplate"]


def test_no_auth_provider_has_null_hint(client):
    body = client.get("/v1/providers").json()
    strict = next(p for p in body if p["name"] == "demo-strict")
    assert strict["authType"] == "none"
    assert strict["authHint"] is None


# ---------- breaker 状态 ----------

def test_breaker_closed_returns_null_cooldown(client):
    body = client.get("/v1/providers").json()
    for p in body:
        assert p["breaker"] == "CLOSED"
        assert p["breakerCooldownSeconds"] is None


def test_breaker_open_exposes_positive_cooldown(client):
    """触发 breaker OPEN 后，cooldown 应为正整数。"""
    breaker = get_breaker()
    # 把 demo-crm 打到 OPEN：默认阈值 5
    for _ in range(10):
        breaker.record_failure("demo-crm")

    body = client.get("/v1/providers").json()
    crm = next(p for p in body if p["name"] == "demo-crm")
    assert crm["breaker"] == "OPEN"
    assert isinstance(crm["breakerCooldownSeconds"], int)
    assert crm["breakerCooldownSeconds"] > 0
    # 默认 open_duration=300s，新打开的 breaker cooldown 不应超过 300
    assert crm["breakerCooldownSeconds"] <= 300

    # 另一个 provider 仍 CLOSED，互不污染
    strict = next(p for p in body if p["name"] == "demo-strict")
    assert strict["breaker"] == "CLOSED"


# ---------- successRateSeries ----------

def _seed_notification(
    id: str,
    *,
    provider: str,
    status: NotificationStatus,
    created_at: datetime,
) -> None:
    with session_scope() as s:
        s.add(Notification(
            id=id,
            idempotency_key=f"k-{id}",
            provider=provider,
            payload={"x": 1},
            status=status,
            attempts=1,
            next_retry_at=created_at,
            created_at=created_at,
        ))


def test_success_rate_series_has_24_buckets(client):
    body = client.get("/v1/providers").json()
    for p in body:
        assert len(p["successRateSeries"]) == 24
        for point in p["successRateSeries"]:
            assert "t" in point and "rate" in point
            assert point["t"].endswith("Z")
            # 没有数据时兜底为 1.0（与 dashboard 同样的"无样本视为完美"语义）
            assert 0.0 <= point["rate"] <= 1.0


def test_success_rate_series_reflects_ratio(client):
    """同一 provider 同一小时灌 4 SUCCEEDED + 1 DEAD_LETTER → 该桶 rate=0.8。"""
    now = datetime.now(UTC)
    for i in range(4):
        _seed_notification(
            f"ok-{i}",
            provider="demo-crm",
            status=NotificationStatus.SUCCEEDED,
            created_at=now,
        )
    _seed_notification(
        "fail-0",
        provider="demo-crm",
        status=NotificationStatus.DEAD_LETTER,
        created_at=now,
    )

    body = client.get("/v1/providers").json()
    crm = next(p for p in body if p["name"] == "demo-crm")
    nonzero = [pt for pt in crm["successRateSeries"] if 0.0 < pt["rate"] < 1.0]
    assert len(nonzero) >= 1
    # 当前小时的桶应该是 0.8
    assert any(abs(pt["rate"] - 0.8) < 1e-6 for pt in crm["successRateSeries"])


def test_success_rate_series_isolates_providers(client):
    """demo-crm 的失败不应污染 demo-strict 的曲线。"""
    now = datetime.now(UTC)
    _seed_notification(
        "crm-fail",
        provider="demo-crm",
        status=NotificationStatus.DEAD_LETTER,
        created_at=now,
    )
    body = client.get("/v1/providers").json()
    strict = next(p for p in body if p["name"] == "demo-strict")
    # demo-strict 没数据：所有 rate 都是 1.0（兜底）
    assert all(pt["rate"] == 1.0 for pt in strict["successRateSeries"])
