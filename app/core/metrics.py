"""极简自实现 Prometheus 文本格式指标。

不引入 prometheus_client，是因为 MVP 只需要文本输出与 4 类指标，自维护
~80 行代码远比拉一个有内部状态、与 multiprocessing 打交道的库简单。
"""
import threading
from collections import defaultdict
from dataclasses import dataclass, field

_DEFAULT_BUCKETS_SECONDS = (0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30)

# 标签键：把 {"provider": "demo-crm"} 表达成可哈希的 sorted tuple
LabelKey = tuple[tuple[str, str], ...]


def _labels_to_str(labels: dict[str, str]) -> str:
    if not labels:
        return ""
    inner = ",".join(f'{k}="{_escape(v)}"' for k, v in sorted(labels.items()))
    return "{" + inner + "}"


def _escape(v: str) -> str:
    return v.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


@dataclass
class Counter:
    name: str
    help: str
    _values: dict[LabelKey, float] = field(default_factory=lambda: defaultdict(float))
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def inc(self, value: float = 1.0, **labels: str) -> None:
        key = tuple(sorted(labels.items()))
        with self._lock:
            self._values[key] += value

    def render(self) -> str:
        lines = [f"# HELP {self.name} {self.help}", f"# TYPE {self.name} counter"]
        with self._lock:
            for key, v in self._values.items():
                lbl = _labels_to_str(dict(key))
                lines.append(f"{self.name}{lbl} {v}")
        return "\n".join(lines)


@dataclass
class Gauge:
    name: str
    help: str
    _values: dict[LabelKey, float] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def set(self, value: float, **labels: str) -> None:
        key = tuple(sorted(labels.items()))
        with self._lock:
            self._values[key] = value

    def render(self) -> str:
        lines = [f"# HELP {self.name} {self.help}", f"# TYPE {self.name} gauge"]
        with self._lock:
            for key, v in self._values.items():
                lbl = _labels_to_str(dict(key))
                lines.append(f"{self.name}{lbl} {v}")
        return "\n".join(lines)


@dataclass
class Histogram:
    name: str
    help: str
    buckets: tuple[float, ...] = _DEFAULT_BUCKETS_SECONDS
    _bucket_counts: dict[LabelKey, list[int]] = field(default_factory=dict)
    _sums: dict[LabelKey, float] = field(default_factory=lambda: defaultdict(float))
    _counts: dict[LabelKey, int] = field(default_factory=lambda: defaultdict(int))
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def observe(self, value: float, **labels: str) -> None:
        key = tuple(sorted(labels.items()))
        with self._lock:
            counts = self._bucket_counts.setdefault(key, [0] * len(self.buckets))
            for i, b in enumerate(self.buckets):
                if value <= b:
                    counts[i] += 1
            self._sums[key] += value
            self._counts[key] += 1

    def render(self) -> str:
        lines = [f"# HELP {self.name} {self.help}", f"# TYPE {self.name} histogram"]
        with self._lock:
            for key, counts in self._bucket_counts.items():
                base_labels = dict(key)
                # observe() 已经把每个 ≤bucket[i] 的次数累加进 counts[i]；
                # 由于 buckets 单调递增，counts 天然单调。
                for i, b in enumerate(self.buckets):
                    lbl = _labels_to_str({**base_labels, "le": str(b)})
                    lines.append(f"{self.name}_bucket{lbl} {counts[i]}")
                lbl_inf = _labels_to_str({**base_labels, "le": "+Inf"})
                lines.append(f"{self.name}_bucket{lbl_inf} {self._counts[key]}")
                lbl_base = _labels_to_str(base_labels)
                lines.append(f"{self.name}_sum{lbl_base} {self._sums[key]}")
                lines.append(f"{self.name}_count{lbl_base} {self._counts[key]}")
        return "\n".join(lines)

    def snapshot(self) -> dict[LabelKey, tuple[list[int], int, float]]:
        """只读快照：每个 label → (bucket_counts 副本, total_count, total_sum)。"""
        with self._lock:
            return {
                k: (list(v), self._counts[k], self._sums[k])
                for k, v in self._bucket_counts.items()
            }


# ---------- 全局指标实例 ----------

notifications_received_total = Counter(
    "notifications_received_total", "Total notifications accepted by intake API"
)
notifications_delivered_total = Counter(
    "notifications_delivered_total", "Total delivery attempts grouped by terminal status"
)
notifications_dlq_total = Counter(
    "notifications_dlq_total", "Total notifications moved to dead letter queue"
)
notification_delivery_duration_seconds = Histogram(
    "notification_delivery_duration_seconds", "HTTP delivery latency to providers"
)
circuit_breaker_state = Gauge(
    "circuit_breaker_state", "Vendor circuit breaker state (0=closed, 1=half_open, 2=open)"
)


def estimate_percentile_seconds(hist: Histogram, p: float) -> float | None:
    """跨所有 label 累加 bucket 后线性插值估算分位数。

    无观测数据返回 None。bucket 边界粒度决定估算精度（默认覆盖 50ms~30s）。
    """
    if not 0 < p < 1:
        raise ValueError("percentile must be in (0, 1)")

    snap = hist.snapshot()
    if not snap:
        return None

    total = sum(count for _, count, _ in snap.values())
    if total == 0:
        return None

    # 按位累加所有 label 的 bucket 计数（observe 已是单调累计形式）。
    merged = [0] * len(hist.buckets)
    for counts, _, _ in snap.values():
        for i, c in enumerate(counts):
            merged[i] += c

    target = p * total
    for i, cum in enumerate(merged):
        if cum >= target:
            lo = hist.buckets[i - 1] if i > 0 else 0.0
            hi = hist.buckets[i]
            prev_cum = merged[i - 1] if i > 0 else 0
            span = cum - prev_cum
            if span <= 0:
                return hi
            frac = (target - prev_cum) / span
            return lo + (hi - lo) * frac

    # 所有累计都 < target：分位落在最后一个 bucket 之外（≥ buckets[-1]）。
    return hist.buckets[-1]


def render_all() -> str:
    parts = [
        notifications_received_total.render(),
        notifications_delivered_total.render(),
        notifications_dlq_total.render(),
        notification_delivery_duration_seconds.render(),
        circuit_breaker_state.render(),
    ]
    return "\n".join(parts) + "\n"
