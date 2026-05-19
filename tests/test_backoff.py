import random
from datetime import UTC, datetime

import pytest

from app.delivery.backoff import (
    JITTER_RATIO,
    base_delay_seconds,
    compute_next_retry_at,
)


@pytest.mark.parametrize(
    "attempts,expected",
    [
        (1, 1),
        (2, 5),
        (3, 25),
        (4, 120),
        (5, 600),
        (6, 3600),
        (7, 21600),
        (8, 86400),
        (99, 86400),  # 超出表也不爆，钳制在最后一项
    ],
)
def test_base_delay_seconds(attempts, expected):
    assert base_delay_seconds(attempts) == expected


def test_base_delay_invalid():
    with pytest.raises(ValueError):
        base_delay_seconds(0)


def test_jitter_within_range():
    rng = random.Random(42)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    base = base_delay_seconds(3)
    for _ in range(200):
        nxt = compute_next_retry_at(3, now=now, rng=rng)
        delta = (nxt - now).total_seconds()
        assert base * (1 - JITTER_RATIO) <= delta <= base * (1 + JITTER_RATIO)


def test_minimum_seconds_for_429():
    """429 限流时应至少等 60 秒。"""
    now = datetime(2026, 1, 1, tzinfo=UTC)
    rng = random.Random(1)
    nxt = compute_next_retry_at(1, now=now, rng=rng, minimum_seconds=60)
    assert (nxt - now).total_seconds() >= 60
