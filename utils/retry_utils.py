from __future__ import annotations

import time
import random
from typing import Callable, TypeVar, Optional

T = TypeVar("T")


def run_with_retries(
    func: Callable[[], T],
    attempts: int = 3,
    base_delay_s: float = 0.5,
    backoff_factor: float = 2.0,
    max_delay_s: float = 8.0,
    on_retry: Optional[Callable[[int, BaseException], None]] = None,
) -> T:
    last_exc: Optional[BaseException] = None
    delay = base_delay_s
    for i in range(1, attempts + 1):
        try:
            return func()
        except BaseException as exc:  # noqa: BLE001
            last_exc = exc
            if i >= attempts:
                break
            if on_retry:
                on_retry(i, exc)
            jitter = random.uniform(0, delay * 0.3)
            time.sleep(min(delay + jitter, max_delay_s))
            delay = min(delay * backoff_factor, max_delay_s)
    assert last_exc is not None
    raise last_exc

