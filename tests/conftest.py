"""测试公共夹具：每个测试用独立 SQLite，配置依赖通过 monkeypatch 注入。"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("CRM_TOKEN", "test-token")
os.environ.setdefault("AD_API_KEY", "test-key")


@pytest.fixture(autouse=True)
def _isolate_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """让每个测试都用独立 SQLite 文件。"""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    # 强制重建 settings + engine
    from app.core import config as cfg_mod
    from app.core import db as db_mod

    cfg_mod.get_settings.cache_clear()
    db_mod.reset_engine()

    db_mod.init_db()
    yield


@pytest.fixture
def providers_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    p = tmp_path / "providers.yaml"
    p.write_text(
        """
demo-crm:
  url: "https://crm.example.com/api/contacts"
  method: POST
  timeout_ms: 1000
  auth:
    type: bearer
    token_env: CRM_TOKEN
  headers:
    Content-Type: application/json
  body_template: |
    {"contact_id": "{{ payload.user_id }}", "status": "{{ payload.event }}"}

demo-strict:
  url: "https://strict.example.com/api"
  method: POST
  timeout_ms: 500
  auth:
    type: none
  headers:
    Content-Type: application/json
  body_template: |
    {"required_field": "{{ payload.must_exist }}"}
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("PROVIDERS_FILE", str(p))
    from app.core import config as cfg_mod
    from app.core.providers import reset_registry

    cfg_mod.get_settings.cache_clear()
    reset_registry()
    return p


@pytest.fixture(autouse=True)
def _reset_breaker():
    from app.delivery.breaker import reset_breaker

    reset_breaker()
    yield
    reset_breaker()
