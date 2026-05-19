"""Vendor 维度的简单熔断器。线程安全（内部用 threading.Lock）。

CLOSED → 连续失败 ≥ threshold → OPEN
OPEN → open_duration 后 → HALF_OPEN（放行 1 单试探）
HALF_OPEN → 成功 → CLOSED；失败 → OPEN（重新计时）
"""
import math
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from functools import lru_cache

from app.core.config import get_settings


class BreakerState(StrEnum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


@dataclass
class _VendorState:
    state: BreakerState = BreakerState.CLOSED
    consecutive_failures: int = 0
    opened_at: datetime | None = None
    half_open_in_flight: bool = False  # HALF_OPEN 期间是否已派发一单试探


@dataclass
class CircuitBreakerRegistry:
    failure_threshold: int
    open_duration: timedelta
    _vendors: dict[str, _VendorState] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def _get(self, vendor: str) -> _VendorState:
        st = self._vendors.get(vendor)
        if st is None:
            st = _VendorState()
            self._vendors[vendor] = st
        return st

    def state_of(self, vendor: str, *, now: datetime | None = None) -> BreakerState:
        with self._lock:
            return self._refresh_state(vendor, now or datetime.now(UTC))

    def allow(self, vendor: str, *, now: datetime | None = None) -> bool:
        """是否允许派发一单。HALF_OPEN 只允许一单试探。"""
        ts = now or datetime.now(UTC)
        with self._lock:
            state = self._refresh_state(vendor, ts)
            if state == BreakerState.CLOSED:
                return True
            if state == BreakerState.OPEN:
                return False
            # HALF_OPEN
            st = self._get(vendor)
            if st.half_open_in_flight:
                return False
            st.half_open_in_flight = True
            return True

    def record_success(self, vendor: str) -> None:
        with self._lock:
            st = self._get(vendor)
            st.state = BreakerState.CLOSED
            st.consecutive_failures = 0
            st.opened_at = None
            st.half_open_in_flight = False

    def record_failure(self, vendor: str, *, now: datetime | None = None) -> None:
        ts = now or datetime.now(UTC)
        with self._lock:
            st = self._get(vendor)
            st.consecutive_failures += 1
            st.half_open_in_flight = False
            if st.state == BreakerState.HALF_OPEN:
                st.state = BreakerState.OPEN
                st.opened_at = ts
                return
            if st.consecutive_failures >= self.failure_threshold:
                st.state = BreakerState.OPEN
                st.opened_at = ts

    def _refresh_state(self, vendor: str, now: datetime) -> BreakerState:
        st = self._get(vendor)
        if st.state == BreakerState.OPEN and st.opened_at is not None:
            if now - st.opened_at >= self.open_duration:
                st.state = BreakerState.HALF_OPEN
                st.half_open_in_flight = False
        return st.state

    def snapshot(self) -> dict[str, BreakerState]:
        with self._lock:
            return {k: v.state for k, v in self._vendors.items()}

    def state_with_cooldown(
        self, vendor: str, *, now: datetime | None = None
    ) -> tuple[BreakerState, int | None]:
        """当前态 + OPEN 时剩余 cooldown 秒数（向上取整）；其余返回 None。"""
        ts = now or datetime.now(UTC)
        with self._lock:
            state = self._refresh_state(vendor, ts)
            st = self._get(vendor)
            if state == BreakerState.OPEN and st.opened_at is not None:
                remaining = (st.opened_at + self.open_duration) - ts
                return state, max(0, math.ceil(remaining.total_seconds()))
            return state, None


@lru_cache(maxsize=1)
def get_breaker() -> CircuitBreakerRegistry:
    s = get_settings()
    return CircuitBreakerRegistry(
        failure_threshold=s.breaker_fail_threshold,
        open_duration=timedelta(seconds=s.breaker_open_duration_seconds),
    )


def reset_breaker() -> None:
    """测试用：清缓存让下次调用按当前配置重建。"""
    get_breaker.cache_clear()
