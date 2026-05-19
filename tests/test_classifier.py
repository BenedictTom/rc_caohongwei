import httpx
import pytest

from app.delivery.classifier import (
    Outcome,
    classify_exception,
    classify_response,
)


def _fake_response(code: int) -> httpx.Response:
    return httpx.Response(status_code=code, request=httpx.Request("POST", "https://x"))


@pytest.mark.parametrize("code", [200, 201, 204, 299])
def test_2xx_success(code):
    r = classify_response(_fake_response(code))
    assert r.outcome == Outcome.SUCCESS


@pytest.mark.parametrize("code", [400, 401, 403, 404, 422])
def test_4xx_dead_letter(code):
    r = classify_response(_fake_response(code))
    assert r.outcome == Outcome.DEAD_LETTER


def test_429_retries_with_minimum():
    r = classify_response(_fake_response(429))
    assert r.outcome == Outcome.RETRY
    assert r.minimum_retry_seconds >= 60


@pytest.mark.parametrize("code", [500, 502, 503, 504])
def test_5xx_retry(code):
    r = classify_response(_fake_response(code))
    assert r.outcome == Outcome.RETRY


def test_timeout_retry():
    exc = httpx.ReadTimeout("slow", request=httpx.Request("POST", "https://x"))
    r = classify_exception(exc)
    assert r.outcome == Outcome.RETRY
    assert r.reason == "timeout"


def test_connect_error_retry():
    exc = httpx.ConnectError("nope", request=httpx.Request("POST", "https://x"))
    r = classify_exception(exc)
    assert r.outcome == Outcome.RETRY
