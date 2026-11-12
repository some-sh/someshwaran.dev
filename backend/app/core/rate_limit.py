"""A small in-memory limiter for failed admin authentication attempts.

Why it exists: the admin API key is the only credential, so repeated wrong
guesses should be slowed down and be visible. Why it is deliberately modest:

* A properly generated key (``secrets.token_urlsafe(32)``, 256 bits) cannot be
  guessed at any rate; this protects against a *weak* key and cuts noise.
* State is per process. With several instances the effective limit is
  ``instances x max_failures`` — still enough to make guessing impractical.
* The client address comes from proxy headers (see security.client_identity),
  which a caller who reaches the app directly can forge. Rotating forged
  addresses defeats the per-address limit. A rule in front of the app (the CDN
  or platform) is the stronger layer where one is available.

Only *failures* are counted. Once an address has hit the limit it is refused
outright for the rest of the window, including with the correct key: otherwise
"429 for a wrong key, 200 for the right one" would still tell a guesser when
they had found it.
"""

from __future__ import annotations

import math
import threading
import time
from collections import OrderedDict, deque
from collections.abc import Callable


class FailureLimiter:
    def __init__(
        self,
        max_failures: int,
        window_seconds: float,
        clock: Callable[[], float] = time.monotonic,
        max_keys: int = 10_000,
    ) -> None:
        self._max = max_failures
        self._window = window_seconds
        self._clock = clock
        self._max_keys = max_keys
        self._failures: OrderedDict[str, deque[float]] = OrderedDict()
        self._lock = threading.Lock()

    def _recent(self, key: str, now: float) -> deque[float] | None:
        attempts = self._failures.get(key)
        if attempts is None:
            return None
        while attempts and now - attempts[0] >= self._window:
            attempts.popleft()
        if not attempts:
            del self._failures[key]
            return None
        return attempts

    def retry_after(self, key: str) -> int | None:
        """Whole seconds until ``key`` may try again, or None if it is not blocked."""
        with self._lock:
            now = self._clock()
            attempts = self._recent(key, now)
            if attempts is None or len(attempts) < self._max:
                return None
            return max(1, math.ceil(attempts[0] + self._window - now))

    def record_failure(self, key: str) -> None:
        with self._lock:
            now = self._clock()
            attempts = self._recent(key, now)
            if attempts is None:
                attempts = self._failures.setdefault(key, deque())
                # Bound memory: a flood of distinct (possibly forged) keys must
                # not grow this without limit. Evict the oldest-seen keys.
                while len(self._failures) > self._max_keys:
                    self._failures.popitem(last=False)
            attempts.append(now)

    def clear(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)
