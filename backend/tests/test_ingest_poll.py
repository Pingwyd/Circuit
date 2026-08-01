import pytest
import respx
from sqlalchemy import func, select

from app.db import async_session
from app.models import LeaderboardSnapshot
from app.osirion.client import OsirionClient
from app.osirion.ingest import poll_leaderboard

LB_EVENT_ID = "test_lb_event_dedupe"
LB_WINDOW_ID = "test_lb_window_dedupe"


def _leaderboard_payload(updated_at: str) -> dict:
    return {
        "success": True,
        "leaderboard": {
            "leaderboardEventId": LB_EVENT_ID,
            "leaderboardEventWindowId": LB_WINDOW_ID,
            "page": 0,
            "totalPages": 1,
            "updatedAt": updated_at,
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
                            "trackedStats": {"eliminations": 5},
                        }
                    ],
                    "unscoredSessions": [],
                }
            ],
        },
    }


async def _snapshot_count() -> int:
    async with async_session() as session:
        result = await session.execute(select(func.count()).select_from(LeaderboardSnapshot))
        return result.scalar_one()


@pytest.mark.asyncio
async def test_poll_new_snapshot_when_updated_at_changes():
    updated_at_v1 = "2026-01-01T14:00:00Z"
    updated_at_v2 = "2026-01-01T15:00:00Z"

    with respx.mock(assert_all_called=True) as respx_mock:
        route = respx_mock.get(
            "https://fnapi.osirion.gg/v1/tournaments/leaderboard",
            params={
                "leaderboardEventId": LB_EVENT_ID,
                "leaderboardEventWindowId": LB_WINDOW_ID,
                "page": "0",
            },
        )
        route.side_effect = [
            respx.MockResponse(json=_leaderboard_payload(updated_at_v1)),
            respx.MockResponse(json=_leaderboard_payload(updated_at_v1)),
            respx.MockResponse(json=_leaderboard_payload(updated_at_v2)),
        ]

        client = OsirionClient()
        try:
            before = await _snapshot_count()

            first = await poll_leaderboard(LB_EVENT_ID, LB_WINDOW_ID, page=0, client=client)
            after_first = await _snapshot_count()

            second = await poll_leaderboard(LB_EVENT_ID, LB_WINDOW_ID, page=0, client=client)
            after_second = await _snapshot_count()

            third = await poll_leaderboard(LB_EVENT_ID, LB_WINDOW_ID, page=0, client=client)
            after_third = await _snapshot_count()
        finally:
            await client.aclose()

    assert first.snapshot_inserted is True
    assert after_first == before + 1

    assert second.snapshot_inserted is False
    assert after_second == after_first

    assert third.snapshot_inserted is True
    assert after_third == after_second + 1
