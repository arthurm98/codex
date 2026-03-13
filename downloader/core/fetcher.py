from __future__ import annotations

import asyncio
import json
import logging
import random
from typing import Any
from urllib.parse import urlsplit

import aiohttp

from downloader.core.rate_limiter import HostRateLimiter
from downloader.core.utils import random_user_agent

logger = logging.getLogger(__name__)
RETRIABLE_STATUSES = {403, 404, 408, 425, 429, 500, 502, 503, 504}


class Fetcher:
    def __init__(self, session: aiohttp.ClientSession, limiter: HostRateLimiter, retries: int = 5) -> None:
        self.session = session
        self.limiter = limiter
        self.retries = retries
        self._primed_hosts: set[str] = set()

    async def get_text(self, url: str, referer: str | None = None) -> str:
        data = await self._request(url, referer=referer)
        return data.decode("utf-8", errors="ignore")

    async def get_json(self, url: str, referer: str | None = None) -> dict[str, Any]:
        return json.loads(await self.get_text(url, referer=referer))

    async def get_bytes(self, url: str, referer: str | None = None) -> bytes:
        return await self._request(url, referer=referer)

    async def _request(self, url: str, referer: str | None = None) -> bytes:
        target = urlsplit(url)
        host = target.netloc
        origin = f"{target.scheme or 'https'}://{host}"
        headers = self._browser_headers(origin, referer=referer)

        last_error: Exception | None = None
        for attempt in range(1, self.retries + 1):
            await self.limiter.wait(host)
            try:
                async with self.session.get(url, headers=headers) as response:
                    if response.status == 403 and host not in self._primed_hosts:
                        await self._prime_host(origin, headers)
                        self._primed_hosts.add(host)
                        raise aiohttp.ClientResponseError(
                            request_info=response.request_info,
                            history=response.history,
                            status=response.status,
                            message="HTTP 403 (retrying with primed cookies)",
                            headers=response.headers,
                        )

                    if response.status in RETRIABLE_STATUSES:
                        raise aiohttp.ClientResponseError(
                            request_info=response.request_info,
                            history=response.history,
                            status=response.status,
                            message=f"HTTP {response.status}",
                            headers=response.headers,
                        )
                    response.raise_for_status()
                    return await response.read()
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt == self.retries:
                    break
                delay = min(8.0, 0.5 * (2 ** (attempt - 1))) + random.uniform(0.0, 0.35)
                logger.warning("Request failed (%s) attempt %s/%s: %s", url, attempt, self.retries, exc)
                await asyncio.sleep(delay)

        assert last_error is not None
        raise last_error

    def _browser_headers(self, origin: str, referer: str | None = None) -> dict[str, str]:
        return {
            "User-Agent": random_user_agent(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": referer or f"{origin}/",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
        }

    async def _prime_host(self, origin: str, headers: dict[str, str]) -> None:
        probe_headers = {
            **headers,
            "Referer": origin,
            "Sec-Fetch-Site": "none",
        }
        try:
            async with self.session.get(origin, headers=probe_headers):
                return
        except Exception as exc:  # noqa: BLE001
            logger.debug("Host priming failed for %s: %s", origin, exc)
