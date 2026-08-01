import asyncio
import heapq
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import IntEnum

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.db import async_session
from app.models import EventWindow, ScoreLocation
from app.osirion.client import OsirionClient
from app.osirion.ingest import PollResult, poll_leaderboard, sync_tournaments

logger = logging.getLogger(__name__)


class JobPriority(IntEnum):
    HIGH = 0
    LOW = 1
    BACKFILL = 2


@dataclass(frozen=True)
class PollKey:
    lb_event_id: str
    lb_window_id: str
    page: int


@dataclass(order=True)
class PollJob:
    sort_index: tuple[int, int]
    key: PollKey = field(compare=False)
    priority: JobPriority = field(compare=False, default=JobPriority.HIGH)


@dataclass(frozen=True)
class WindowTarget:
    event_window_id: str
    lb_event_id: str
    lb_window_id: str
    is_main: bool


class PollScheduler:
    CYCLE_SECONDS = 15
    HIGH_INTERVAL_BASE = 75.0
    HIGH_INTERVAL_MIN = 60.0
    HIGH_INTERVAL_MAX = 120.0
    LOW_INTERVAL = 300.0
    TOURNAMENT_STALE = timedelta(hours=6)
    BACKFILL_WINDOW = timedelta(minutes=10)
    HIGH_PAGE_COUNT = 10

    def __init__(self) -> None:
        self._client = OsirionClient()
        self._apscheduler = AsyncIOScheduler()
        self._queue: list[PollJob] = []
        self._seq = 0
        self._pending: set[PollKey] = set()
        self._last_polled: dict[PollKey, datetime] = {}
        self._total_pages: dict[tuple[str, str], int] = {}
        self._backfill_pages: dict[str, set[int]] = {}
        self._backfilled: set[str] = set()
        self._last_tournament_sync: datetime | None = None
        self._lb_request_times: list[float] = []
        self._lock = asyncio.Lock()
        self._started = False

    @property
    def client(self) -> OsirionClient:
        return self._client

    def start(self) -> None:
        if self._started:
            return
        self._apscheduler.add_job(
            self._cycle,
            "interval",
            seconds=self.CYCLE_SECONDS,
            id="poll_cycle",
            max_instances=1,
            coalesce=True,
        )
        self._apscheduler.add_job(
            self._log_rate,
            "interval",
            seconds=60,
            id="rate_log",
            max_instances=1,
            coalesce=True,
        )
        self._apscheduler.start()
        self._started = True
        logger.info("Poll scheduler started (cycle=%ds)", self.CYCLE_SECONDS)

    async def stop(self) -> None:
        if not self._started:
            return
        self._apscheduler.shutdown(wait=False)
        await self._client.aclose()
        self._started = False
        logger.info("Poll scheduler stopped")

    async def enqueue_deep_page(
        self,
        lb_event_id: str,
        lb_window_id: str,
        page: int,
    ) -> None:
        key = PollKey(lb_event_id, lb_window_id, page)
        async with self._lock:
            self._push_job(key, JobPriority.HIGH)

    def _effective_high_interval(self) -> float:
        depth = len(self._queue) + len(self._pending)
        if depth > 50:
            return self.HIGH_INTERVAL_MAX
        if depth > 20:
            return 90.0
        return self.HIGH_INTERVAL_BASE

    def _is_due(self, key: PollKey, interval: float) -> bool:
        last = self._last_polled.get(key)
        if last is None:
            return True
        elapsed = (datetime.now(timezone.utc) - last).total_seconds()
        return elapsed >= interval

    def _push_job(self, key: PollKey, priority: JobPriority) -> None:
        if key in self._pending:
            return
        self._seq += 1
        heapq.heappush(
            self._queue,
            PollJob(sort_index=(int(priority), self._seq), key=key, priority=priority),
        )
        self._pending.add(key)

    async def _maybe_sync_tournaments(self) -> None:
        now = datetime.now(timezone.utc)
        if (
            self._last_tournament_sync is not None
            and now - self._last_tournament_sync < self.TOURNAMENT_STALE
        ):
            return
        try:
            counts = await sync_tournaments(client=self._client)
            self._last_tournament_sync = now
            logger.info(
                "Tournament catalog refreshed: %d tournaments, %d windows, %d score locations",
                counts.tournaments,
                counts.event_windows,
                counts.score_locations,
            )
        except Exception:
            logger.exception("Tournament sync failed; continuing poll cycle")

    async def _fetch_window_targets(self) -> tuple[list[WindowTarget], list[WindowTarget]]:
        now = datetime.now(timezone.utc)
        backfill_cutoff = now - self.BACKFILL_WINDOW

        async with async_session() as session:
            stmt = select(
                EventWindow.event_window_id,
                ScoreLocation.leaderboard_event_id,
                ScoreLocation.leaderboard_event_window_id,
                ScoreLocation.is_main,
                EventWindow.begin_time,
                EventWindow.end_time,
            ).join(ScoreLocation, ScoreLocation.event_window_id == EventWindow.event_window_id)
            rows = (await session.execute(stmt)).all()

        live: list[WindowTarget] = []
        recently_ended: list[WindowTarget] = []
        for row in rows:
            target = WindowTarget(
                event_window_id=row.event_window_id,
                lb_event_id=row.leaderboard_event_id,
                lb_window_id=row.leaderboard_event_window_id,
                is_main=row.is_main,
            )
            if row.begin_time <= now <= row.end_time:
                live.append(target)
            elif backfill_cutoff <= row.end_time <= now:
                recently_ended.append(target)
        return live, recently_ended

    def _enqueue_live_jobs(self, live: list[WindowTarget]) -> None:
        high_interval = self._effective_high_interval()
        for target in live:
            if not target.is_main:
                continue
            lb_pair = (target.lb_event_id, target.lb_window_id)
            for page in range(self.HIGH_PAGE_COUNT):
                key = PollKey(target.lb_event_id, target.lb_window_id, page)
                if self._is_due(key, high_interval):
                    self._push_job(key, JobPriority.HIGH)

            total = self._total_pages.get(lb_pair)
            if total is None:
                continue
            for page in range(self.HIGH_PAGE_COUNT, total):
                key = PollKey(target.lb_event_id, target.lb_window_id, page)
                if self._is_due(key, self.LOW_INTERVAL):
                    self._push_job(key, JobPriority.LOW)

    def _enqueue_backfill_jobs(self, recently_ended: list[WindowTarget]) -> None:
        for target in recently_ended:
            if not target.is_main:
                continue
            if target.lb_window_id in self._backfilled:
                continue

            lb_pair = (target.lb_event_id, target.lb_window_id)
            total = self._total_pages.get(lb_pair)
            done = self._backfill_pages.get(target.lb_window_id, set())

            if total is None:
                if 0 not in done:
                    key = PollKey(target.lb_event_id, target.lb_window_id, 0)
                    self._push_job(key, JobPriority.BACKFILL)
                continue

            for page in range(total):
                if page in done:
                    continue
                key = PollKey(target.lb_event_id, target.lb_window_id, page)
                self._push_job(key, JobPriority.BACKFILL)

    async def _execute_job(self, job: PollJob) -> None:
        key = job.key
        started = time.monotonic()
        try:
            result = await poll_leaderboard(
                key.lb_event_id,
                key.lb_window_id,
                page=key.page,
                client=self._client,
            )
            self._record_request(started)
            self._on_poll_success(key, job.priority, result)
        except Exception:
            logger.exception(
                "Poll failed for %s/%s page=%d",
                key.lb_event_id,
                key.lb_window_id,
                key.page,
            )

    def _record_request(self, started: float) -> None:
        self._lb_request_times.append(started)
        now = time.monotonic()
        self._lb_request_times = [t for t in self._lb_request_times if now - t < 60]

    def _on_poll_success(self, key: PollKey, priority: JobPriority, result: PollResult) -> None:
        self._last_polled[key] = datetime.now(timezone.utc)
        lb_pair = (key.lb_event_id, key.lb_window_id)
        self._total_pages[lb_pair] = result.total_pages

        if priority == JobPriority.BACKFILL:
            pages = self._backfill_pages.setdefault(key.lb_window_id, set())
            pages.add(key.page)
            if len(pages) >= result.total_pages:
                self._backfilled.add(key.lb_window_id)
                logger.info("Backfill complete for window %s (%d pages)", key.lb_window_id, result.total_pages)

    async def _drain_queue(self) -> int:
        executed = 0
        while self._queue:
            job = heapq.heappop(self._queue)
            self._pending.discard(job.key)
            await self._execute_job(job)
            executed += 1
        return executed

    async def _cycle(self) -> None:
        async with self._lock:
            await self._maybe_sync_tournaments()
            live, recently_ended = await self._fetch_window_targets()
            self._enqueue_live_jobs(live)
            self._enqueue_backfill_jobs(recently_ended)
            executed = await self._drain_queue()
            if executed:
                logger.info(
                    "Poll cycle: live_windows=%d ended_windows=%d jobs_executed=%d queue_stretch_interval=%.0fs",
                    len({t.lb_window_id for t in live if t.is_main}),
                    len({t.lb_window_id for t in recently_ended if t.is_main}),
                    executed,
                    self._effective_high_interval(),
                )

    async def _log_rate(self) -> None:
        now = time.monotonic()
        self._lb_request_times = [t for t in self._lb_request_times if now - t < 60]
        count = len(self._lb_request_times)
        logger.info("Leaderboard requests last minute: %d (ceiling 54)", count)

    async def run_cycle_once(self) -> int:
        """Manual/test hook: run a single scheduler cycle."""
        async with self._lock:
            live, recently_ended = await self._fetch_window_targets()
            self._enqueue_live_jobs(live)
            self._enqueue_backfill_jobs(recently_ended)
            return await self._drain_queue()


_scheduler: PollScheduler | None = None


def get_scheduler() -> PollScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = PollScheduler()
    return _scheduler


async def enqueue_deep_page(lb_event_id: str, lb_window_id: str, page: int) -> None:
    await get_scheduler().enqueue_deep_page(lb_event_id, lb_window_id, page)
