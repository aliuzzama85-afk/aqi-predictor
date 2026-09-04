"""Shared retry helper for flaky Hopsworks read calls."""
import logging
import time
from typing import Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


def read_with_retry(read_fn: Callable[[], T], attempts: int = 3, backoff_seconds: float = 15) -> T:
    """Retries a zero-arg Hopsworks read call (e.g. `lambda: fg.read()`) on failure.

    Hopsworks' offline read path (Arrow Flight Query Service) can transiently
    fail with server-side errors unrelated to the query itself; retrying with
    a short backoff usually succeeds within a couple of attempts.
    """
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return read_fn()
        except Exception as exc:
            last_exc = exc
            logger.warning("Hopsworks read attempt %d/%d failed: %s", attempt, attempts, exc)
            if attempt < attempts:
                time.sleep(backoff_seconds)
    raise last_exc
