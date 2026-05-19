"""错误分类：决定一次投递结果是 SUCCESS / RETRY / DEAD_LETTER。"""
from dataclasses import dataclass
from enum import StrEnum

import httpx


class Outcome(StrEnum):
    SUCCESS = "SUCCESS"
    RETRY = "RETRY"
    DEAD_LETTER = "DEAD_LETTER"


@dataclass(frozen=True)
class ClassifiedResult:
    outcome: Outcome
    reason: str
    minimum_retry_seconds: int = 0  # 429 时强制最少等多久
    response_summary: str | None = None


def classify_response(resp: httpx.Response) -> ClassifiedResult:
    code = resp.status_code
    summary = f"HTTP {code} {resp.reason_phrase}"
    if 200 <= code < 300:
        return ClassifiedResult(Outcome.SUCCESS, "2xx", response_summary=summary)
    if code == 429:
        return ClassifiedResult(
            Outcome.RETRY, "rate_limited_429", minimum_retry_seconds=60, response_summary=summary
        )
    if 400 <= code < 500:
        return ClassifiedResult(
            Outcome.DEAD_LETTER, f"client_error_{code}", response_summary=summary
        )
    if 500 <= code < 600:
        return ClassifiedResult(Outcome.RETRY, f"server_error_{code}", response_summary=summary)
    # 1xx/3xx：罕见且不应作为最终态返回；保守按 RETRY 处理
    return ClassifiedResult(Outcome.RETRY, f"unexpected_status_{code}", response_summary=summary)


def classify_exception(exc: Exception) -> ClassifiedResult:
    if isinstance(exc, httpx.TimeoutException):
        return ClassifiedResult(Outcome.RETRY, "timeout")
    if isinstance(exc, httpx.ConnectError):
        return ClassifiedResult(Outcome.RETRY, "connect_error")
    if isinstance(exc, httpx.NetworkError):
        return ClassifiedResult(Outcome.RETRY, "network_error")
    if isinstance(exc, httpx.HTTPError):
        return ClassifiedResult(Outcome.RETRY, "http_error")
    # 模板渲染等本地错误由调用方包装为特定异常并跳过此函数
    return ClassifiedResult(Outcome.RETRY, f"unknown:{type(exc).__name__}")
