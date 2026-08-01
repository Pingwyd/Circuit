import asyncio
import time

import pytest
import respx

from app.osirion.client import OsirionClient, RateLimiter
from app.schemas import TournamentLeaderboardDataResponse, TournamentsDataResponse

TOURNAMENTS_PAYLOAD = {
    "success": True,
    "region": "EU",
    "tournaments": [
        {
            "eventId": "evt1",
            "eventGroup": "grp",
            "regions": ["EU"],
            "platforms": ["Windows"],
            "displayData": {
                "tournamentDisplayId": "td1",
                "posterFrontImage": "https://example.com/poster.png",
            },
            "eventWindows": [
                {
                    "eventWindowId": "win1",
                    "beginTime": "2026-01-01T12:00:00Z",
                    "endTime": "2026-01-01T15:00:00Z",
                    "round": 1,
                    "scoreLocations": [
                        {
                            "leaderboardEventId": "lb1",
                            "leaderboardEventWindowId": "lbw1",
                            "isMain": True,
                            "payoutTables": [],
                            "scoringRules": [],
                        }
                    ],
                    "additionalRequirements": [],
                    "requireAllTokens": [],
                    "requireAnyTokens": [],
                    "requireNoneTokensCaller": [],
                    "requireAllTokensCaller": [],
                    "requireAnyTokensCaller": [],
                    "playlistId": None,
                    "matchCap": None,
                    "metadata": {},
                }
            ],
            "metadata": {},
        }
    ],
}

LEADERBOARD_PAYLOAD = {
    "success": True,
    "leaderboard": {
        "leaderboardEventId": "lb1",
        "leaderboardEventWindowId": "lbw1",
        "page": 0,
        "totalPages": 1,
        "updatedAt": "2026-01-01T14:00:00Z",
        "entries": [
            {
                "teamId": "team1",
                "players": [
                    {
                        "accountId": "abc123def45678901234567890123456",
                        "username": "player",
                        "flagToken": "US",
                    }
                ],
                "pointsEarned": 10,
                "score": 100,
                "rank": 1,
                "percentile": 99.9,
                "sessionHistory": [
                    {
                        "sessionId": "s1",
                        "endTime": "2026-01-01T13:00:00Z",
                        "trackedStats": {"eliminations": 5, "note": "live"},
                    }
                ],
                "unscoredSessions": [],
            }
        ],
    },
}


@pytest.mark.asyncio
async def test_get_tournaments_parses():
    with respx.mock(assert_all_called=True) as respx_mock:
        respx_mock.get(
            "https://fnapi.osirion.gg/v1/tournaments",
            params={"includeHistoricData": "false", "region": "EU"},
        ).respond(json=TOURNAMENTS_PAYLOAD)
        client = OsirionClient()
        data = await client.get_tournaments(region="EU")
        parsed = TournamentsDataResponse.model_validate(data)

        assert parsed.success is True
        assert parsed.region == "EU"
        sl = parsed.tournaments[0].event_windows[0].score_locations[0]
        assert sl.leaderboard_event_id == "lb1"
        assert sl.leaderboard_event_window_id == "lbw1"
        assert parsed.tournaments[0].display_data.poster_front_image is not None


@pytest.mark.asyncio
async def test_get_leaderboard_parses():
    with respx.mock(assert_all_called=True) as respx_mock:
        respx_mock.get(
            "https://fnapi.osirion.gg/v1/tournaments/leaderboard",
            params={
                "leaderboardEventId": "lb1",
                "leaderboardEventWindowId": "lbw1",
                "page": "0",
            },
        ).respond(json=LEADERBOARD_PAYLOAD)
        client = OsirionClient()
        data = await client.get_leaderboard("lb1", "lbw1", page=0)
        parsed = TournamentLeaderboardDataResponse.model_validate(data)

        assert parsed.success is True
        entry = parsed.leaderboard.entries[0]
        assert entry.team_id == "team1"
        assert entry.players[0].username == "player"
        assert entry.session_history[0].tracked_stats["eliminations"] == 5
        assert parsed.leaderboard.updated_at.isoformat().startswith("2026-01-01")


@pytest.mark.asyncio
async def test_rate_limiter_blocks_past_ceiling(monkeypatch):
    limiter = RateLimiter(60)
    assert limiter.capacity == 54

    clock = {"now": 1000.0}
    monkeypatch.setattr(time, "monotonic", lambda: clock["now"])

    async def advancing_sleep(duration: float) -> None:
        clock["now"] += duration

    monkeypatch.setattr(asyncio, "sleep", advancing_sleep)

    timestamps: list[float] = []
    for _ in range(54):
        await limiter.acquire()
        timestamps.append(clock["now"])

    assert len(timestamps) == 54
    assert all(t == 1000.0 for t in timestamps)

    time_before_wait = clock["now"]
    await limiter.acquire()
    assert clock["now"] > time_before_wait

    window_start = timestamps[0]
    hits_in_window = [t for t in timestamps if t - window_start < 60]
    assert len(hits_in_window) == 54


@pytest.mark.asyncio
async def test_client_methods_use_expected_limiter_buckets():
    client = OsirionClient()
    assert client._rl["default"].capacity == 90
    assert client._rl["leaderboard"].capacity == 54
    assert client._rl["account"].capacity == 45
