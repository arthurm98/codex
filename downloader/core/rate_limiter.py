from __future__ import annotations

import asyncio
import time
from collections import defaultdict


class HostRateLimiter:
    def __init__(self, min_delay: float) -> None:
        self.min_delay = max(min_delay, 0.0)
        self._last_hit: dict[str, float] = defaultdict(float)
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def wait(self, host: str) -> None:
        lock = self._locks[host]
        async with lock:
            now = time.monotonic()
            elapsed = now - self._last_hit[host]
            if elapsed < self.min_delay:
                await asyncio.sleep(self.min_delay - elapsed)
            self._last_hit[host] = time.monotonic()
