import asyncio
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.osirion.ingest import PollResult
from app.scheduler import JobPriority, PollKey, PollScheduler, WindowTarget


def _poll_result(total_pages: int = 3) -> PollResult:
    return PollResult(
        snapshot_inserted=True,
        entries_on_page=10,
        current_upserted=10,
        players_upserted=10,
        entry_players_upserted=10,
        source_updated_at=datetime(2026, 1, 1, 14, 0, tzinfo=timezone.utc),
        total_pages=total_pages,
    )


@pytest.mark.asyncio
async def test_high_interval_stretches_with_queue_depth():
    scheduler = PollScheduler()
    assert scheduler._effective_high_interval() == 75.0

    for i in range(25):
        scheduler._push_job(PollKey("lb", f"w{i}", 0), JobPriority.HIGH)
    assert scheduler._effective_high_interval() == 90.0

    for i in range(25, 55):
        scheduler._push_job(PollKey("lb", f"w{i}", 0), JobPriority.HIGH)
    assert scheduler._effective_high_interval() == 120.0


@pytest.mark.asyncio
async def test_backfill_runs_once_per_window():
    scheduler = PollScheduler()
    target = WindowTarget("ew1", "lb1", "win1", is_main=True)

    poll_mock = AsyncMock(return_value=_poll_result(total_pages=2))
    with patch("app.scheduler.poll_leaderboard", poll_mock):
        scheduler._enqueue_backfill_jobs([target])
        assert len(scheduler._queue) == 1
        await scheduler._drain_queue()
        assert poll_mock.await_count == 1
        assert scheduler._total_pages[("lb1", "win1")] == 2

        scheduler._enqueue_backfill_jobs([target])
        await scheduler._drain_queue()
        assert poll_mock.await_count == 2
        assert "win1" in scheduler._backfilled

        scheduler._enqueue_backfill_jobs([target])
        await scheduler._drain_queue()
        assert poll_mock.await_count == 2


@pytest.mark.asyncio
async def test_enqueue_deep_page_uses_high_priority():
    scheduler = PollScheduler()
    await scheduler.enqueue_deep_page("lb1", "win1", 42)
    assert len(scheduler._queue) == 1
    job = scheduler._queue[0]
    assert job.priority == JobPriority.HIGH
    assert job.key.page == 42


@pytest.mark.asyncio
async def test_rate_log_uses_rolling_minute_window():
    scheduler = PollScheduler()
    base = time.monotonic()
    for i in range(10):
        scheduler._record_request(base + i)
    assert len(scheduler._lb_request_times) == 10

    scheduler._lb_request_times = [t for t in scheduler._lb_request_times if time.monotonic() - t < 60]
    assert len(scheduler._lb_request_times) <= 10


@pytest.mark.asyncio
async def test_client_rate_limiter_caps_burst_requests():
    """Prove the shared leaderboard limiter allows at most 54 acquires per 60s window."""
    from app.osirion.client import OsirionClient

    client = OsirionClient()
    clock = {"now": 1000.0}

    async def advancing_sleep(duration: float) -> None:
        clock["now"] += duration

    with patch("app.osirion.client.asyncio.sleep", advancing_sleep):
        with patch("app.osirion.client.time.monotonic", lambda: clock["now"]):
            for _ in range(54):
                await client._rl["leaderboard"].acquire()
            before = clock["now"]
            await client._rl["leaderboard"].acquire()
            assert clock["now"] > before

    await client.aclose()


@pytest.mark.asyncio
async def test_poll_failure_does_not_abort_cycle():
    scheduler = PollScheduler()
    scheduler._push_job(PollKey("lb1", "win1", 0), JobPriority.HIGH)
    scheduler._push_job(PollKey("lb2", "win2", 0), JobPriority.HIGH)

    poll_mock = AsyncMock(side_effect=[RuntimeError("boom"), _poll_result()])
    with patch("app.scheduler.poll_leaderboard", poll_mock):
        executed = await scheduler._drain_queue()

    assert executed == 2
    assert poll_mock.await_count == 2


@pytest.mark.asyncio
async def test_fetch_window_targets_failure_does_not_abort_cycle():
    scheduler = PollScheduler()
    scheduler._push_job(PollKey("lb1", "win1", 0), JobPriority.HIGH)

    poll_mock = AsyncMock(return_value=_poll_result())
    with patch("app.scheduler.poll_leaderboard", poll_mock):
        with patch.object(
            scheduler,
            "_fetch_window_targets",
            AsyncMock(side_effect=RuntimeError("db down")),
        ):
            await scheduler._cycle()

    assert poll_mock.await_count == 1


@pytest.mark.asyncio
async def test_scheduler_start_and_stop():
    scheduler = PollScheduler()
    scheduler.start()
    assert scheduler._started is True
    await scheduler.stop()
    assert scheduler._started is False
