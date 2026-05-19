"""GET /v1/notifications 与 /v1/dead-letters 列表查询的端到端测试。

直接 ORM 写入测试数据，绕过投递链路；只验查询拼装、过滤、分页与 camelCase 出口。
"""
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import routes_dlq, routes_notifications
from app.core.db import session_scope
from app.models.notification import Notification, NotificationStatus


@pytest.fixture
def app(providers_yaml):  # noqa: ARG001
    app = FastAPI()
    app.include_router(routes_notifications.router)
    app.include_router(routes_dlq.router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


def _make(
    id: str,
    *,
    provider: str = "demo-crm",
    status: NotificationStatus = NotificationStatus.SUCCEEDED,
    attempts: int = 1,
    payload: dict | None = None,
    created_at: datetime | None = None,
    idempotency_key: str | None = None,
    last_error: str | None = None,
) -> Notification:
    now = created_at or datetime.now(UTC)
    return Notification(
        id=id,
        idempotency_key=idempotency_key or f"key-{id}",
        provider=provider,
        payload=payload or {"user_id": 1, "event": "x"},
        status=status,
        attempts=attempts,
        next_retry_at=now,
        created_at=now,
        last_error=last_error,
    )


def _seed(rows: list[Notification]) -> None:
    with session_scope() as s:
        for r in rows:
            s.add(r)


# ---------- list shape ----------

def test_list_empty_returns_page_zero(client):
    resp = client.get("/v1/notifications")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"items": [], "total": 0, "limit": 25, "offset": 0}


def test_list_returns_camelcase_fields(client):
    _seed([_make("ntf_001")])
    body = client.get("/v1/notifications").json()
    assert body["total"] == 1
    item = body["items"][0]
    # camelCase 出口（alias_generator）
    for k in ("idempotencyKey", "createdAt", "nextRetryAt"):
        assert k in item
    # snake_case 不应出现
    assert "idempotency_key" not in item
    assert "created_at" not in item


# ---------- filters ----------

def test_filter_by_status(client):
    _seed([
        _make("a", status=NotificationStatus.SUCCEEDED),
        _make("b", status=NotificationStatus.PENDING),
        _make("c", status=NotificationStatus.DEAD_LETTER),
    ])
    body = client.get("/v1/notifications?status=PENDING").json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == "b"


def test_filter_by_provider(client):
    _seed([
        _make("a", provider="demo-crm"),
        _make("b", provider="demo-strict"),
    ])
    body = client.get("/v1/notifications?provider=demo-strict").json()
    assert [i["id"] for i in body["items"]] == ["b"]


def test_filter_by_q_matches_id(client):
    _seed([_make("ntf_alpha"), _make("ntf_beta")])
    body = client.get("/v1/notifications?q=alpha").json()
    assert [i["id"] for i in body["items"]] == ["ntf_alpha"]


def test_filter_by_q_matches_idempotency_key(client):
    _seed([
        _make("a", idempotency_key="order-2025-0001"),
        _make("b", idempotency_key="payment-9999"),
    ])
    body = client.get("/v1/notifications?q=payment").json()
    assert [i["id"] for i in body["items"]] == ["b"]


def test_filter_by_q_matches_payload_substring(client):
    _seed([
        _make("a", payload={"sku": "BANANA-1"}),
        _make("b", payload={"sku": "APPLE-1"}),
    ])
    body = client.get("/v1/notifications?q=BANANA").json()
    assert [i["id"] for i in body["items"]] == ["a"]


def test_filter_by_time_range(client):
    base = datetime(2026, 5, 18, 10, tzinfo=UTC)
    _seed([
        _make("old", created_at=base - timedelta(hours=5)),
        _make("mid", created_at=base),
        _make("new", created_at=base + timedelta(hours=5)),
    ])
    # 只取 base ± 1h 内；TestClient 的 params 会自动 URL-encode（含 + → %2B）
    body = client.get(
        "/v1/notifications",
        params={
            "fromTs": (base - timedelta(hours=1)).isoformat(),
            "toTs": (base + timedelta(hours=1)).isoformat(),
        },
    ).json()
    assert [i["id"] for i in body["items"]] == ["mid"]


# ---------- pagination ----------

def test_pagination_limit_and_offset(client):
    base = datetime(2026, 5, 18, tzinfo=UTC)
    _seed([
        _make(f"id-{i}", created_at=base + timedelta(seconds=i))
        for i in range(7)
    ])
    page1 = client.get("/v1/notifications?limit=3&offset=0").json()
    page2 = client.get("/v1/notifications?limit=3&offset=3").json()
    page3 = client.get("/v1/notifications?limit=3&offset=6").json()

    assert page1["total"] == 7
    assert page2["total"] == 7
    assert len(page1["items"]) == 3
    assert len(page2["items"]) == 3
    assert len(page3["items"]) == 1
    # 全部 id 互不重叠且按 created_at desc 排序
    ids = [i["id"] for i in page1["items"] + page2["items"] + page3["items"]]
    assert ids == sorted(ids, reverse=True)


def test_limit_validation_rejects_zero(client):
    resp = client.get("/v1/notifications?limit=0")
    assert resp.status_code == 422


def test_limit_validation_rejects_too_large(client):
    resp = client.get("/v1/notifications?limit=999")
    assert resp.status_code == 422


# ---------- /v1/dead-letters：共用 query_notifications，重点验 status 隐含过滤 ----------

def test_dead_letters_only_returns_dead_letter(client):
    _seed([
        _make("ok", status=NotificationStatus.SUCCEEDED),
        _make("dlq", status=NotificationStatus.DEAD_LETTER, last_error="server_error"),
    ])
    body = client.get("/v1/dead-letters").json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["id"] == "dlq"
    assert item["status"] == "DEAD_LETTER"
    assert item["lastError"] == "server_error"  # camelCase 兼带验证


def test_dead_letters_accepts_fromTs_alias(client):
    """旧版本是 from/to，新版用 fromTs/toTs alias——确认前端 NotificationsQuery 字段名直通。"""
    base = datetime(2026, 5, 18, tzinfo=UTC)
    _seed([
        _make("old", status=NotificationStatus.DEAD_LETTER, created_at=base - timedelta(days=10)),
        _make("new", status=NotificationStatus.DEAD_LETTER, created_at=base),
    ])
    body = client.get(
        "/v1/dead-letters",
        params={"fromTs": (base - timedelta(hours=1)).isoformat()},
    ).json()
    assert [i["id"] for i in body["items"]] == ["new"]
