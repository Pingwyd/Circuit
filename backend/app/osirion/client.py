import asyncio
import logging
import time

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class RateLimiter:
    """Sliding 60s window, blocks until a slot is free under the ceiling."""

    def __init__(self, max_per_min: int):
        self.capacity = int(max_per_min * 0.9)  # 90% ceiling
        self._hits: list[float] = []
        self._lock = asyncio.Lock()

    def count_in_window(self) -> int:
        now = time.monotonic()
        return len([t for t in self._hits if now - t < 60])

    def utilization(self) -> float:
        if self.capacity == 0:
            return 0.0
        return self.count_in_window() / self.capacity

    async def acquire(self) -> None:
        async with self._lock:
            while True:
                now = time.monotonic()
                self._hits = [t for t in self._hits if now - t < 60]
                if len(self._hits) < self.capacity:
                    self._hits.append(now)
                    return
                await asyncio.sleep(60 - (now - self._hits[0]) + 0.05)


class OsirionClient:
    def __init__(self) -> None:
        headers: dict[str, str] = {}
        if settings.osirion_api_key:
            headers["Authorization"] = f"Bearer {settings.osirion_api_key}"
        self._c = httpx.AsyncClient(
            base_url=settings.osirion_base_url,
            timeout=30.0,
            headers=headers,
        )
        self._rl = {
            "account": RateLimiter(50),
            "leaderboard": RateLimiter(60),
            "default": RateLimiter(100),
        }

    def rate_limit_stats(self) -> dict[str, dict[str, float | int]]:
        return {
            bucket: {
                "count": limiter.count_in_window(),
                "ceiling": limiter.capacity,
                "utilization": round(limiter.utilization(), 4),
            }
            for bucket, limiter in self._rl.items()
        }

    async def _get(self, path: str, cls: str, params: dict | None = None):
        limiter = self._rl[cls]
        await limiter.acquire()
        page = params.get("page") if params else None
        for attempt in range(3):
            started = time.monotonic()
            try:
                r = await self._c.get(path, params=params)
                latency_ms = (time.monotonic() - started) * 1000
                r.raise_for_status()
                logger.info(
                    "osirion_call endpoint=%s bucket=%s page=%s latency_ms=%.1f "
                    "bucket_count=%d bucket_ceiling=%d attempt=%d",
                    path,
                    cls,
                    page,
                    latency_ms,
                    limiter.count_in_window(),
                    limiter.capacity,
                    attempt + 1,
                )
                return r.json()
            except (httpx.TimeoutException, httpx.HTTPStatusError) as exc:
                latency_ms = (time.monotonic() - started) * 1000
                logger.warning(
                    "osirion_call_failed endpoint=%s bucket=%s page=%s latency_ms=%.1f "
                    "bucket_count=%d bucket_ceiling=%d attempt=%d error=%s",
                    path,
                    cls,
                    page,
                    latency_ms,
                    limiter.count_in_window(),
                    limiter.capacity,
                    attempt + 1,
                    type(exc).__name__,
                )
                if attempt == 2:
                    raise
                await asyncio.sleep(2**attempt)

    async def get_tournaments(self, region=None, historic=False, lang=None):
        params: dict[str, str] = {"includeHistoricData": str(historic).lower()}
        if region:
            params["region"] = region
        if lang:
            params["lang"] = lang
        return await self._get("/v1/tournaments", "default", params)

    async def get_leaderboard(self, lb_event_id, lb_window_id, page=0):
        return await self._get(
            "/v1/tournaments/leaderboard",
            "leaderboard",
            {
                "leaderboardEventId": lb_event_id,
                "leaderboardEventWindowId": lb_window_id,
                "page": page,
            },
        )

    async def lookup_by_name(self, display_name, platform=None):
        params: dict[str, str] = {"displayName": display_name}
        if platform:
            params["platform"] = platform
        return await self._get("/v1/accounts/lookup-by-display-name", "account", params)

    async def aclose(self) -> None:
        await self._c.aclose()
