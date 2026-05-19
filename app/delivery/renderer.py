"""Provider 适配：把通知的 payload + provider 配置渲染成最终 HTTP 请求。"""
from dataclasses import dataclass
from typing import Any

from jinja2 import Environment, StrictUndefined, TemplateError

from app.core.providers import ProviderConfig


class TemplateRenderError(Exception):
    """模板渲染失败——不可重试，应直接进 DLQ。"""


@dataclass(frozen=True)
class RenderedRequest:
    method: str
    url: str
    headers: dict[str, str]
    body: str
    timeout_ms: int


_env = Environment(
    autoescape=False,
    undefined=StrictUndefined,
    keep_trailing_newline=False,
)


def render(provider: ProviderConfig, payload: dict[str, Any]) -> RenderedRequest:
    headers = dict(provider.headers)

    if provider.auth.type == "bearer":
        token = provider.auth.resolve_token() or ""
        headers["Authorization"] = f"Bearer {token}"
    elif provider.auth.type == "header":
        token = provider.auth.resolve_token() or ""
        if provider.auth.name:
            headers[provider.auth.name] = token

    try:
        body = _env.from_string(provider.body_template).render(payload=payload)
    except TemplateError as e:
        raise TemplateRenderError(f"render error: {e}") from e
    except Exception as e:  # 包含 UndefinedError
        raise TemplateRenderError(f"render error: {e}") from e

    return RenderedRequest(
        method=provider.method,
        url=provider.url,
        headers=headers,
        body=body,
        timeout_ms=provider.timeout_ms,
    )
