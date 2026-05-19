"""GET /v1/metrics/summary：聚合接口的端到端测试。

直接 ORM 写数据库 + 给 Histogram 注入 observation，验聚合形状。
"""
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import routes_metrics
from app.core import metrics
from app.core.db import session_scope
from app.models.notification import Notification, NotificationStatus


@pytest.fixture
def app(providers_yaml):  # noqa: ARG001
    app = FastAPI()
    app.include_router(routes_metrics.router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture(autouse=True)
def _reset_histogram():
    """每个测试前清空 P95 histogram 的内部计数。"""
    h = metrics.notification_delivery_duration_seconds
    with h._lock:
        h._bucket_counts.clear()
        h._sums.clear()
        h._counts.clear()
    yield


def _make(
    id: str,
    *,
    provider: str = "demo-crm",
    status: NotificationStatus = NotificationStatus.SUCCEEDED,
    created_at: datetime | None = None,
) -> Notification:
    now = created_at or datetime.now(UTC)
    return Notification(
        id=id,
        idempotency_key=f"k-{id}",
        provider=provider,
        payload={"x": 1},
        status=status,
        attempts=1,
        next_retry_at=now,
        created_at=now,
    )


def _seed(rows: list[Notification]) -> None:
    with session_scope() as s:
        for r in rows:
            s.add(r)


# ---------- 空数据 fallback ----------

def test_empty_data_returns_safe_defaults(client):
    body = client.get("/v1/metrics/summary").json()
    # 字段全 camelCase
    assert set(body.keys()) == {
        "successRate", "inflight", "dlqTotal",
        "p95LatencyMs", "trend", "byProvider",
    }
    # 24h 没数据：分母为 0，successRate 兜底 1.0（不是 NaN / 0）
    assert body["successRate"] == 1.0
    assert body["inflight"] == 0
    assert body["dlqTotal"] == 0
    assert body["p95LatencyMs"] == 0
    assert len(body["trend"]) == 24
    # 24 个桶全零，但都有时间戳
    for point in body["trend"]:
        assert point["succeeded"] == 0
        assert point["failed"] == 0
        assert point["inflight"] == 0
        assert point["t"].endswith("Z")
    assert body["byProvider"] == []


# ---------- 数值聚合 ----------

def test_success_rate_is_succeeded_over_succ_plus_failed(client):
    # 8 SUCCEEDED + 2 DEAD_LETTER → success_rate = 0.8
    _seed([_make(f"s-{i}", status=NotificationStatus.SUCCEEDED) for i in range(8)])
    _seed([_make(f"d-{i}", status=NotificationStatus.DEAD_LETTER) for i in range(2)])
    body = client.get("/v1/metrics/summary").json()
    assert body["successRate"] == 0.8
    assert body["dlqTotal"] == 2


def test_inflight_counts_pending_and_in_flight(client):
    _seed([
        _make("a", status=NotificationStatus.PENDING),
        _make("b", status=NotificationStatus.IN_FLIGHT),
        _make("c", status=NotificationStatus.SUCCEEDED),
    ])
    body = client.get("/v1/metrics/summary").json()
    assert body["inflight"] == 2


def test_by_provider_groups_correctly(client):
    _seed([
        _make("a", provider="demo-crm", status=NotificationStatus.SUCCEEDED),
        _make("b", provider="demo-crm", status=NotificationStatus.SUCCEEDED),
        _make("c", provider="demo-crm", status=NotificationStatus.DEAD_LETTER),
        _make("d", provider="demo-strict", status=NotificationStatus.SUCCEEDED),
    ])
    body = client.get("/v1/metrics/summary").json()
    by_p = {p["provider"]: p for p in body["byProvider"]}
    assert by_p["demo-crm"]["succeeded"] == 2
    assert by_p["demo-crm"]["dlq"] == 1
    assert by_p["demo-strict"]["succeeded"] == 1
    assert by_p["demo-strict"]["dlq"] == 0


# ---------- trend 24h 桶 ----------

def test_trend_buckets_align_to_hour(client):
    """灌一笔到当前小时，验证至少有一个非零桶且时间戳格式正确。"""
    now = datetime.now(UTC)
    _seed([_make("now", status=NotificationStatus.SUCCEEDED, created_at=now)])
    body = client.get("/v1/metrics/summary").json()
    nonzero = [p for p in body["trend"] if p["succeeded"] > 0]
    assert len(nonzero) >= 1
    # 时间戳格式：YYYY-MM-DDTHH:00:00Z
    import re
    for p in body["trend"]:
        assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:00:00Z$", p["t"])


def test_trend_excludes_data_older_than_24h(client):
    """超过 24h 的数据不应进入 trend，但仍计入 dlqTotal（全表）。"""
    long_ago = datetime.now(UTC) - timedelta(days=2)
    _seed([_make("ancient", status=NotificationStatus.DEAD_LETTER, created_at=long_ago)])
    body = client.get("/v1/metrics/summary").json()
    assert all(p["succeeded"] == 0 and p["failed"] == 0 for p in body["trend"])
    # 但全表 dlqTotal 仍然计上
    assert body["dlqTotal"] == 1


# ---------- p95 来自 Histogram ----------

def test_p95_pulls_from_delivery_histogram(client):
    h = metrics.notification_delivery_duration_seconds
    # 90 笔快 + 10 笔慢，total=100，target=95；前 4 个 bucket 累计 90 < 95，
    # 第 5 个 bucket（≤1.0）累计 100 ≥ 95，命中后落在 (0.5, 1.0] 区间。
    for _ in range(90):
        h.observe(0.05, provider="demo-crm")
    for _ in range(10):
        h.observe(0.9, provider="demo-crm")
    body = client.get("/v1/metrics/summary").json()
    assert body["p95LatencyMs"] > 500
    assert body["p95LatencyMs"] <= 1000


def test_p95_zero_when_no_observations(client):
    body = client.get("/v1/metrics/summary").json()
    assert body["p95LatencyMs"] == 0
