import httpx
import logging

import pytest
import respx
from fastapi.testclient import TestClient

from app.main import app
from app.osirion.client import OsirionClient, RateLimiter

LEADERBOARD_PAYLOAD = {
    "success": True,
    "leaderboard": {
        "leaderboardEventId": "lb1",
        "leaderboardEventWindowId": "lbw1",
        "page": 0,
        "totalPages": 1,
        "updatedAt": "2026-01-01T14:00:00Z",
        "entries": [],
    },
}


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.mark.asyncio
async def test_osirion_call_logs_endpoint_latency_and_bucket_count(caplog):
    caplog.set_level(logging.INFO, logger="app.osirion.client")
    with respx.mock(assert_all_called=True) as respx_mock:
        respx_mock.get("https://fnapi.osirion.gg/v1/tournaments/leaderboard").respond(
            json=LEADERBOARD_PAYLOAD
        )
        osirion = OsirionClient()
        await osirion.get_leaderboard("lb1", "lbw1", page=3)
        await osirion.aclose()

    messages = [r.message for r in caplog.records if r.name == "app.osirion.client"]
    assert any("osirion_call endpoint=/v1/tournaments/leaderboard" in m for m in messages)
    assert any("bucket=leaderboard" in m for m in messages)
    assert any("page=3" in m for m in messages)
    assert any("latency_ms=" in m for m in messages)
    assert any("bucket_count=1" in m for m in messages)
    assert any("bucket_ceiling=54" in m for m in messages)


def test_rate_limiter_exposes_window_count_and_utilization():
    limiter = RateLimiter(60)
    assert limiter.count_in_window() == 0
    assert limiter.utilization() == 0.0


def test_admin_metrics_returns_expected_fields(client: TestClient):
    response = client.get("/admin/metrics")
    assert response.status_code == 200
    body = response.json()
    assert "liveMainWindows" in body
    assert "snapshotsLastHour" in body
    assert "rateLimits" in body
    assert "lastTournamentSync" in body
    for bucket in ("account", "leaderboard", "default"):
        assert bucket in body["rateLimits"]
        entry = body["rateLimits"][bucket]
        assert "count" in entry
        assert "ceiling" in entry
        assert "utilization" in entry
        assert entry["count"] <= entry["ceiling"]


@pytest.mark.asyncio
async def test_forced_upstream_error_is_logged_and_retried(caplog):
    caplog.set_level(logging.WARNING, logger="app.osirion.client")
    with respx.mock(assert_all_called=True) as respx_mock:
        route = respx_mock.get("https://fnapi.osirion.gg/v1/tournaments/leaderboard")
        route.side_effect = [
            httpx.Response(500),
            httpx.Response(500),
            httpx.Response(500),
        ]
        osirion = OsirionClient()
        with pytest.raises(Exception):
            await osirion.get_leaderboard("lb1", "lbw1", page=0)
        await osirion.aclose()

    failures = [r.message for r in caplog.records if "osirion_call_failed" in r.message]
    assert len(failures) == 3


@pytest.mark.asyncio
async def test_rate_limit_utilization_stays_at_or_under_ceiling():
    from unittest.mock import patch

    client = OsirionClient()
    clock = {"now": 1000.0}

    async def advancing_sleep(duration: float) -> None:
        clock["now"] += duration

    with patch("app.osirion.client.asyncio.sleep", advancing_sleep):
        with patch("app.osirion.client.time.monotonic", lambda: clock["now"]):
            for _ in range(54):
                await client._rl["leaderboard"].acquire()
            stats = client.rate_limit_stats()
            assert stats["leaderboard"]["count"] == 54
            assert stats["leaderboard"]["count"] <= stats["leaderboard"]["ceiling"]
            assert stats["leaderboard"]["utilization"] <= 1.0

    await client.aclose()
