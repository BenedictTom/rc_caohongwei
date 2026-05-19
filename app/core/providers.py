import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.core.config import get_settings


@dataclass(frozen=True)
class AuthConfig:
    type: str  # "bearer" | "header" | "none"
    token_env: str | None = None
    name: str | None = None  # header 鉴权时的 header 名

    def resolve_token(self) -> str | None:
        if self.type == "none":
            return None
        if not self.token_env:
            return None
        return os.environ.get(self.token_env)


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    url: str
    method: str
    timeout_ms: int
    headers: dict[str, str]
    body_template: str
    auth: AuthConfig


@dataclass
class ProviderRegistry:
    providers: dict[str, ProviderConfig] = field(default_factory=dict)

    def get(self, name: str) -> ProviderConfig | None:
        return self.providers.get(name)

    def has(self, name: str) -> bool:
        return name in self.providers

    def names(self) -> list[str]:
        return list(self.providers.keys())


def _parse_provider(name: str, raw: dict[str, Any]) -> ProviderConfig:
    auth_raw = raw.get("auth") or {"type": "none"}
    auth = AuthConfig(
        type=auth_raw.get("type", "none"),
        token_env=auth_raw.get("token_env"),
        name=auth_raw.get("name"),
    )
    return ProviderConfig(
        name=name,
        url=raw["url"],
        method=raw.get("method", "POST").upper(),
        timeout_ms=int(raw.get("timeout_ms", get_settings().http_default_timeout_ms)),
        headers=dict(raw.get("headers") or {}),
        body_template=raw.get("body_template", ""),
        auth=auth,
    )


def load_providers(path: Path | None = None) -> ProviderRegistry:
    """加载并校验 providers.yaml；启动期不可恢复错误直接抛出，让进程拒绝起来。"""
    settings = get_settings()
    file_path = path or settings.providers_file
    if not file_path.exists():
        raise FileNotFoundError(f"providers file not found: {file_path}")

    with open(file_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    if not isinstance(raw, dict):
        raise ValueError("providers.yaml top-level must be a mapping")

    registry = ProviderRegistry()
    for name, item in raw.items():
        if not isinstance(item, dict):
            raise ValueError(f"provider {name!r} config must be a mapping")
        cfg = _parse_provider(name, item)
        if cfg.auth.type != "none":
            if not cfg.auth.token_env:
                raise ValueError(f"provider {name!r} auth missing token_env")
            if not os.environ.get(cfg.auth.token_env):
                raise RuntimeError(
                    f"provider {name!r} requires env {cfg.auth.token_env}, but it is not set"
                )
        registry.providers[name] = cfg

    return registry


@lru_cache(maxsize=1)
def get_registry() -> ProviderRegistry:
    return load_providers()


def reset_registry() -> None:
    """测试用：清缓存让下次调用按当前配置重新加载。"""
    get_registry.cache_clear()
