"""Histogram.snapshot + estimate_percentile_seconds 的单元测试。

测的是 P95 估算的"形状"是否合理（落在期望的 bucket 区间），不要求精确数值
——bucket 边界离散决定了误差天花板。
"""
import pytest

from app.core.metrics import Histogram, estimate_percentile_seconds


# ---------- Histogram.snapshot ----------

def test_snapshot_empty_returns_empty_dict():
    h = Histogram(name="t", help="t")
    assert h.snapshot() == {}


def test_snapshot_records_counts_and_sum():
    h = Histogram(name="t", help="t", buckets=(0.1, 0.5, 1.0))
    h.observe(0.05, provider="a")
    h.observe(0.3, provider="a")
    h.observe(0.8, provider="a")

    snap = h.snapshot()
    key = (("provider", "a"),)
    assert key in snap
    counts, total, total_sum = snap[key]
    # 累计形式：≤0.1 一笔，≤0.5 两笔（0.05 + 0.3），≤1.0 三笔
    assert counts == [1, 2, 3]
    assert total == 3
    assert abs(total_sum - (0.05 + 0.3 + 0.8)) < 1e-9


def test_snapshot_returns_copy_not_reference():
    """改 snapshot 不能影响内部状态。"""
    h = Histogram(name="t", help="t", buckets=(0.1, 0.5))
    h.observe(0.05, provider="a")
    snap = h.snapshot()
    counts, *_ = snap[(("provider", "a"),)]
    counts[0] = 999
    # 再观察一次后 bucket 内部计数应该按 1 + 1 演进，不受外部改动影响
    h.observe(0.05, provider="a")
    snap2 = h.snapshot()
    assert snap2[(("provider", "a"),)][0] == [2, 2]


def test_snapshot_isolates_labels():
    h = Histogram(name="t", help="t", buckets=(0.1, 0.5, 1.0))
    h.observe(0.05, provider="a")
    h.observe(0.6, provider="b")
    snap = h.snapshot()
    assert snap[(("provider", "a"),)][1] == 1
    assert snap[(("provider", "b"),)][1] == 1


# ---------- estimate_percentile_seconds ----------

def test_percentile_empty_histogram_returns_none():
    h = Histogram(name="t", help="t")
    assert estimate_percentile_seconds(h, 0.95) is None


def test_percentile_invalid_p_raises():
    h = Histogram(name="t", help="t")
    h.observe(0.1)
    with pytest.raises(ValueError):
        estimate_percentile_seconds(h, 0.0)
    with pytest.raises(ValueError):
        estimate_percentile_seconds(h, 1.0)
    with pytest.raises(ValueError):
        estimate_percentile_seconds(h, 1.5)


def test_percentile_single_observation_falls_in_first_bucket():
    h = Histogram(name="t", help="t", buckets=(0.1, 0.5, 1.0))
    h.observe(0.05)  # 落第一个 bucket [0, 0.1]
    p = estimate_percentile_seconds(h, 0.5)
    assert p is not None
    assert 0.0 <= p <= 0.1


def test_percentile_p99_lands_in_top_bucket():
    h = Histogram(name="t", help="t", buckets=(0.1, 0.5, 1.0))
    # 95 笔低延迟 + 5 笔高延迟：p=0.99 → target=99，前两个 bucket 累计 95
    # 不够，落到 (0.5, 1.0] 这个 bucket 内做插值。
    for _ in range(95):
        h.observe(0.05)
    for _ in range(5):
        h.observe(0.9)
    p = estimate_percentile_seconds(h, 0.99)
    assert p is not None
    assert 0.5 < p <= 1.0


def test_percentile_aggregates_across_labels():
    """跨 label 累加：两个 provider 各 50 笔，p50 应在合并后的中位 bucket 区间。"""
    h = Histogram(name="t", help="t", buckets=(0.1, 0.5, 1.0))
    for _ in range(50):
        h.observe(0.05, provider="a")  # 全在第一个 bucket
    for _ in range(50):
        h.observe(0.6, provider="b")  # 全在第三个 bucket
    p = estimate_percentile_seconds(h, 0.5)
    assert p is not None
    # 合并后前 50 笔在 [0, 0.1]，第 51 笔起跳到 (0.5, 1.0]；p=0.5 → target=50
    # 第一个 bucket cum=50，target=50 → 命中第一个 bucket 上界附近
    assert 0.0 <= p <= 0.1


def test_percentile_overflow_returns_last_bucket_boundary():
    """所有观察都比最后一个 bucket 还大时，估算返回 buckets[-1]。"""
    h = Histogram(name="t", help="t", buckets=(0.1, 0.5))
    # observe(2.0) → 没有任何 bucket 计数会增加（因为 2.0 > 0.5），
    # 但 _counts 增加 1。merged 累计永远 < target，走 fallback。
    h.observe(2.0)
    p = estimate_percentile_seconds(h, 0.95)
    assert p == 0.5
