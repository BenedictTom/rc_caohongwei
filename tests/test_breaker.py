from datetime import UTC, datetime, timedelta

from app.delivery.breaker import BreakerState, CircuitBreakerRegistry


def test_closed_to_open_after_threshold():
    b = CircuitBreakerRegistry(failure_threshold=3, open_duration=timedelta(seconds=60))
    assert b.allow("v")
    for _ in range(3):
        b.record_failure("v")
    assert b.state_of("v") == BreakerState.OPEN
    assert b.allow("v") is False


def test_open_to_half_open_after_duration():
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    b = CircuitBreakerRegistry(failure_threshold=2, open_duration=timedelta(seconds=10))
    for _ in range(2):
        b.record_failure("v", now=t0)
    assert b.state_of("v", now=t0) == BreakerState.OPEN

    later = t0 + timedelta(seconds=11)
    assert b.allow("v", now=later)  # HALF_OPEN 放行一单
    assert b.allow("v", now=later) is False  # 第二单被拒


def test_half_open_success_to_closed():
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    b = CircuitBreakerRegistry(failure_threshold=2, open_duration=timedelta(seconds=10))
    b.record_failure("v", now=t0)
    b.record_failure("v", now=t0)
    later = t0 + timedelta(seconds=11)
    assert b.allow("v", now=later)
    b.record_success("v")
    assert b.state_of("v") == BreakerState.CLOSED
    assert b.allow("v")


def test_half_open_failure_back_to_open():
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    b = CircuitBreakerRegistry(failure_threshold=2, open_duration=timedelta(seconds=10))
    b.record_failure("v", now=t0)
    b.record_failure("v", now=t0)
    later = t0 + timedelta(seconds=11)
    assert b.allow("v", now=later)
    b.record_failure("v", now=later)
    assert b.state_of("v", now=later) == BreakerState.OPEN
    assert b.allow("v", now=later) is False


# ---------- state_with_cooldown ----------

def test_cooldown_closed_returns_none():
    b = CircuitBreakerRegistry(failure_threshold=3, open_duration=timedelta(seconds=60))
    state, cd = b.state_with_cooldown("v")
    assert state == BreakerState.CLOSED
    assert cd is None


def test_cooldown_open_returns_remaining_seconds():
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    b = CircuitBreakerRegistry(failure_threshold=2, open_duration=timedelta(seconds=60))
    b.record_failure("v", now=t0)
    b.record_failure("v", now=t0)
    # 触发 OPEN 后 0 秒查询：剩余 60s
    state, cd = b.state_with_cooldown("v", now=t0)
    assert state == BreakerState.OPEN
    assert cd == 60

    # 25 秒后查询：剩余 35s（math.ceil 后仍 35）
    state, cd = b.state_with_cooldown("v", now=t0 + timedelta(seconds=25))
    assert state == BreakerState.OPEN
    assert cd == 35


def test_cooldown_open_expired_auto_to_half_open():
    """超过 open_duration 时，state_with_cooldown 触发 OPEN→HALF_OPEN 转移。"""
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    b = CircuitBreakerRegistry(failure_threshold=2, open_duration=timedelta(seconds=10))
    b.record_failure("v", now=t0)
    b.record_failure("v", now=t0)
    later = t0 + timedelta(seconds=20)
    state, cd = b.state_with_cooldown("v", now=later)
    assert state == BreakerState.HALF_OPEN
    assert cd is None


def test_cooldown_half_open_returns_none():
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    b = CircuitBreakerRegistry(failure_threshold=2, open_duration=timedelta(seconds=10))
    b.record_failure("v", now=t0)
    b.record_failure("v", now=t0)
    later = t0 + timedelta(seconds=11)
    # 先用 allow 把状态推进到 HALF_OPEN
    b.allow("v", now=later)
    state, cd = b.state_with_cooldown("v", now=later)
    assert state == BreakerState.HALF_OPEN
    assert cd is None


def test_cooldown_unknown_vendor_treated_as_closed():
    b = CircuitBreakerRegistry(failure_threshold=3, open_duration=timedelta(seconds=60))
    state, cd = b.state_with_cooldown("never-seen")
    assert state == BreakerState.CLOSED
    assert cd is None
