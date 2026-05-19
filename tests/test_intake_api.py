"""Intake API 集成测试：用 FastAPI TestClient + 隔离 SQLite。

注意：lifespan 会启动 worker（需要 providers.yaml）。我们手工绕开 lifespan，
只挂载路由——验证 intake 行为本身。投递链路在 test_delivery_e2e 里覆盖。
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import routes_dlq, routes_health, routes_metrics, routes_notifications


@pytest.fixture
def app(providers_yaml):  # noqa: ARG001  fixture 触发 monkeypatch + reset_registry
    app = FastAPI()
    app.include_router(routes_notifications.router)
    app.include_router(routes_dlq.router)
    app.include_router(routes_health.router)
    app.include_router(routes_metrics.router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


def test_submit_returns_202(client):
    resp = client.post(
        "/v1/notifications",
        headers={"Idempotency-Key": "k-1"},
        json={"provider": "demo-crm", "payload": {"user_id": 1, "event": "registered"}},
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["id"].startswith("ntf_")
    assert body["status"] == "PENDING"


def test_submit_idempotency_returns_same_id(client):
    payload = {"provider": "demo-crm", "payload": {"user_id": 2, "event": "paid"}}
    a = client.post("/v1/notifications", headers={"Idempotency-Key": "k-2"}, json=payload).json()
    b = client.post("/v1/notifications", headers={"Idempotency-Key": "k-2"}, json=payload).json()
    assert a["id"] == b["id"]


def test_submit_unknown_provider_400(client):
    resp = client.post(
        "/v1/notifications",
        headers={"Idempotency-Key": "k-3"},
        json={"provider": "nonexistent", "payload": {}},
    )
    assert resp.status_code == 400
    assert "unknown provider" in resp.json()["detail"]


def test_submit_missing_field_400(client):
    resp = client.post(
        "/v1/notifications",
        headers={"Idempotency-Key": "k-4"},
        json={"payload": {"x": 1}},
    )
    assert resp.status_code == 422  # FastAPI 模型校验 → 422


def test_submit_payload_too_large_413(client):
    big = "x" * (70 * 1024)
    resp = client.post(
        "/v1/notifications",
        headers={"Idempotency-Key": "k-5"},
        json={"provider": "demo-crm", "payload": {"data": big}},
    )
    assert resp.status_code == 413


def test_submit_without_idempotency_key_uses_fallback(client):
    payload = {"provider": "demo-crm", "payload": {"user_id": 9, "event": "x"}}
    a = client.post("/v1/notifications", json=payload).json()
    b = client.post("/v1/notifications", json=payload).json()
    # 完全相同的 (provider, payload) → 兜底键命中 → 同一 id
    assert a["id"] == b["id"]


def test_dead_letters_endpoint_empty(client):
    resp = client.get("/v1/dead-letters")
    assert resp.status_code == 200
    assert resp.json()["items"] == []


def test_submit_first_call_duplicated_false(client):
    resp = client.post(
        "/v1/notifications",
        headers={"Idempotency-Key": "dup-1"},
        json={"provider": "demo-crm", "payload": {"user_id": 1, "event": "x"}},
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["duplicated"] is False
    # camelCase 出口校验：alias_generator 把内部 snake_case 转成 camelCase
    assert "duplicated" in body and "id" in body and "status" in body


def test_submit_idempotency_hit_marks_duplicated_true(client):
    payload = {"provider": "demo-crm", "payload": {"user_id": 2, "event": "y"}}
    a = client.post("/v1/notifications", headers={"Idempotency-Key": "dup-2"}, json=payload).json()
    b = client.post("/v1/notifications", headers={"Idempotency-Key": "dup-2"}, json=payload).json()
    assert a["duplicated"] is False
    assert b["duplicated"] is True
    assert a["id"] == b["id"]


def test_submit_fallback_key_repeat_marks_duplicated_true(client):
    """不带 Idempotency-Key 时按 sha256(payload) 兜底，重发也应命中 duplicated。"""
    payload = {"provider": "demo-crm", "payload": {"user_id": 7, "event": "x"}}
    a = client.post("/v1/notifications", json=payload).json()
    b = client.post("/v1/notifications", json=payload).json()
    assert a["duplicated"] is False
    assert b["duplicated"] is True
    assert a["id"] == b["id"]


def test_metrics_endpoint(client):
    client.post(
        "/v1/notifications",
        headers={"Idempotency-Key": "m-1"},
        json={"provider": "demo-crm", "payload": {"user_id": 1, "event": "x"}},
    )
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "notifications_received_total" in resp.text
