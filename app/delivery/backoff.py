"""退避序列：1s, 5s, 25s, 2m, 10m, 1h, 6h, 24h（共 8 次，~31h），±20% jitter。

`compute_next_retry_at` 是纯函数，便于单测。
"""
import random
from datetime import UTC, datetime, timedelta

# 索引 = attempts（首次失败后 attempts=1）；最后一项是 attempts=8 时的占位（实际此时已进 DLQ）
_BACKOFF_SECONDS: tuple[int, ...] = (
    1,           # attempts=1 → 1s
    5,           # attempts=2 → 5s
    25,          # attempts=3 → 25s
    2 * 60,      # attempts=4 → 2m
    10 * 60,     # attempts=5 → 10m
    60 * 60,     # attempts=6 → 1h
    6 * 60 * 60, # attempts=7 → 6h
    24 * 60 * 60,# attempts=8 → 24h（仅在 max>8 时用到）
)

JITTER_RATIO = 0.2


def base_delay_seconds(attempts: int) -> int:
    """attempts: 已尝试次数（≥1）。返回不含 jitter 的退避秒数。"""
    if attempts < 1:
        raise ValueError("attempts must be >= 1")
    idx = min(attempts - 1, len(_BACKOFF_SECONDS) - 1)
    return _BACKOFF_SECONDS[idx]


def compute_next_retry_at(
    attempts: int,
    *,
    now: datetime | None = None,
    rng: random.Random | None = None,
    minimum_seconds: int = 0,
) -> datetime:
    """根据当前 attempts 计算下一次重试时间（含 ±20% jitter）。

    minimum_seconds: 用于 429 限流时强制至少等待若干秒。
    """
    base = base_delay_seconds(attempts)
    rnd = rng or random
    factor = 1.0 + rnd.uniform(-JITTER_RATIO, JITTER_RATIO)
    delay = max(base * factor, float(minimum_seconds))
    current = now or datetime.now(UTC)
    return current + timedelta(seconds=delay)
