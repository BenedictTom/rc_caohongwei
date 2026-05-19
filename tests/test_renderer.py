
import pytest

from app.core.providers import AuthConfig, ProviderConfig
from app.delivery.renderer import TemplateRenderError, render


def _make_provider(template: str, auth_type: str = "none", token_env: str | None = None):
    return ProviderConfig(
        name="t",
        url="https://x.example.com/y",
        method="POST",
        timeout_ms=1000,
        headers={"Content-Type": "application/json"},
        body_template=template,
        auth=AuthConfig(type=auth_type, token_env=token_env, name="X-Api-Key"),
    )


def test_render_basic():
    p = _make_provider('{"u": "{{ payload.user }}"}')
    r = render(p, {"user": "alice"})
    assert '"u": "alice"' in r.body
    assert r.method == "POST"


def test_render_missing_field_raises():
    p = _make_provider('{"u": "{{ payload.missing }}"}')
    with pytest.raises(TemplateRenderError):
        render(p, {"user": "alice"})


def test_render_bearer_auth_injects_header(monkeypatch):
    monkeypatch.setenv("MY_TOKEN", "secret123")
    p = _make_provider('{}', auth_type="bearer", token_env="MY_TOKEN")
    r = render(p, {})
    assert r.headers["Authorization"] == "Bearer secret123"


def test_render_header_auth(monkeypatch):
    monkeypatch.setenv("MY_KEY", "k-001")
    p = _make_provider('{}', auth_type="header", token_env="MY_KEY")
    r = render(p, {})
    assert r.headers["X-Api-Key"] == "k-001"
