"""FailureLimiter, driven by a fake clock so no test sleeps."""

from app.core.rate_limit import FailureLimiter


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def _limiter(clock: Clock, max_failures: int = 3, window: float = 60, max_keys: int = 100):
    return FailureLimiter(max_failures, window, clock=clock, max_keys=max_keys)


def test_not_blocked_until_the_limit_is_reached():
    clock = Clock()
    limiter = _limiter(clock)

    for _ in range(2):
        limiter.record_failure("a")
        assert limiter.retry_after("a") is None
    limiter.record_failure("a")

    assert limiter.retry_after("a") == 60


def test_retry_after_counts_down_from_the_oldest_failure_in_the_window():
    clock = Clock()
    limiter = _limiter(clock)
    for _ in range(3):
        limiter.record_failure("a")

    clock.now += 45

    assert limiter.retry_after("a") == 15


def test_the_block_lifts_when_the_window_passes():
    clock = Clock()
    limiter = _limiter(clock)
    for _ in range(3):
        limiter.record_failure("a")

    clock.now += 60

    assert limiter.retry_after("a") is None


def test_it_is_a_sliding_window_so_old_failures_stop_counting():
    clock = Clock()
    limiter = _limiter(clock)
    limiter.record_failure("a")
    limiter.record_failure("a")
    clock.now += 61  # both are now outside the window

    limiter.record_failure("a")
    limiter.record_failure("a")

    assert limiter.retry_after("a") is None  # only 2 recent failures


def test_clear_forgets_a_key():
    clock = Clock()
    limiter = _limiter(clock)
    for _ in range(3):
        limiter.record_failure("a")

    limiter.clear("a")

    assert limiter.retry_after("a") is None


def test_keys_are_independent():
    clock = Clock()
    limiter = _limiter(clock)
    for _ in range(3):
        limiter.record_failure("attacker")

    assert limiter.retry_after("attacker") is not None
    assert limiter.retry_after("someone-else") is None


def test_memory_is_bounded_against_a_flood_of_distinct_keys():
    clock = Clock()
    limiter = _limiter(clock, max_keys=50)

    for index in range(500):
        limiter.record_failure(f"forged-{index}")

    assert len(limiter._failures) <= 50  # noqa: SLF001 - asserting the memory bound
    # The newest keys are the ones kept.
    limiter.record_failure("forged-499")
    assert "forged-499" in limiter._failures  # noqa: SLF001
