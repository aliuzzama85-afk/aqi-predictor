"""Tests for aqi_predictor.hopsworks_utils.read_with_retry."""
import pytest

from aqi_predictor.hopsworks_utils import read_with_retry


def test_read_with_retry_succeeds_after_transient_failures():
    calls = {"count": 0}

    def flaky_read():
        calls["count"] += 1
        if calls["count"] < 3:
            raise RuntimeError("transient Hopsworks error")
        return "ok"

    result = read_with_retry(flaky_read, attempts=3, backoff_seconds=0)

    assert result == "ok"
    assert calls["count"] == 3


def test_read_with_retry_raises_after_exhausting_attempts():
    def always_fails():
        raise RuntimeError("persistent Hopsworks error")

    with pytest.raises(RuntimeError, match="persistent Hopsworks error"):
        read_with_retry(always_fails, attempts=2, backoff_seconds=0)
