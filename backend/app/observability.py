from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EventWindow, LeaderboardSnapshot, ScoreLocation
from app.osirion.client import OsirionClient


async def count_live_main_windows(session: AsyncSession) -> int:
    now = datetime.now(timezone.utc)
    stmt = (
        select(func.count())
        .select_from(ScoreLocation)
        .join(EventWindow, ScoreLocation.event_window_id == EventWindow.event_window_id)
        .where(
            EventWindow.begin_time <= now,
            EventWindow.end_time >= now,
            ScoreLocation.is_main.is_(True),
        )
    )
    return int((await session.execute(stmt)).scalar_one())


async def count_snapshots_last_hour(session: AsyncSession) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
    stmt = (
        select(func.count())
        .select_from(LeaderboardSnapshot)
        .where(LeaderboardSnapshot.captured_at >= cutoff)
    )
    return int((await session.execute(stmt)).scalar_one())


def merge_rate_limit_stats(*clients: OsirionClient) -> dict[str, dict[str, float | int]]:
    if not clients:
        return {}
    merged: dict[str, dict[str, float | int]] = {}
    for bucket in clients[0]._rl:
        count = sum(client._rl[bucket].count_in_window() for client in clients)
        ceiling = clients[0]._rl[bucket].capacity
        merged[bucket] = {
            "count": count,
            "ceiling": ceiling,
            "utilization": round(count / ceiling, 4) if ceiling else 0.0,
        }
    return merged
