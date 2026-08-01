from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api_schemas import (
    LeaderboardEntryItem,
    LeaderboardLoadingResponse,
    LeaderboardReadyResponse,
)
from app.deps import get_db
from app.models import LeaderboardCurrent, LeaderboardSnapshot
from app.scheduler import enqueue_deep_page

router = APIRouter(tags=["leaderboards"])

PAGE_SIZE = 100


@router.get("/leaderboard/{lb_event_id}/{lb_window_id}")
async def get_leaderboard(
    lb_event_id: str,
    lb_window_id: str,
    page: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> Response:
    snapshot_exists = (
        await db.execute(
            select(LeaderboardSnapshot.id)
            .where(
                LeaderboardSnapshot.leaderboard_event_id == lb_event_id,
                LeaderboardSnapshot.leaderboard_event_window_id == lb_window_id,
                LeaderboardSnapshot.page == page,
            )
            .limit(1)
        )
    ).scalar_one_or_none()

    if snapshot_exists is None:
        await enqueue_deep_page(lb_event_id, lb_window_id, page)
        body = LeaderboardLoadingResponse(
            leaderboard_event_id=lb_event_id,
            leaderboard_event_window_id=lb_window_id,
            page=page,
        )
        return JSONResponse(status_code=202, content=body.model_dump(by_alias=True))

    rank_min = page * PAGE_SIZE + 1
    rank_max = (page + 1) * PAGE_SIZE
    rows = (
        await db.execute(
            select(LeaderboardCurrent)
            .where(
                LeaderboardCurrent.leaderboard_event_id == lb_event_id,
                LeaderboardCurrent.leaderboard_event_window_id == lb_window_id,
                LeaderboardCurrent.rank >= rank_min,
                LeaderboardCurrent.rank <= rank_max,
            )
            .order_by(LeaderboardCurrent.rank)
        )
    ).scalars().all()

    source_updated_at = (
        await db.execute(
            select(func.max(LeaderboardCurrent.source_updated_at)).where(
                LeaderboardCurrent.leaderboard_event_id == lb_event_id,
                LeaderboardCurrent.leaderboard_event_window_id == lb_window_id,
            )
        )
    ).scalar_one()

    entries = [
        LeaderboardEntryItem(
            team_id=row.team_id,
            rank=row.rank,
            score=float(row.score) if row.score is not None else None,
            points_earned=float(row.points_earned) if row.points_earned is not None else None,
            percentile=float(row.percentile) if row.percentile is not None else None,
            players=row.players if isinstance(row.players, list) else [],
            session_history=row.session_history if isinstance(row.session_history, list) else [],
        )
        for row in rows
    ]

    body = LeaderboardReadyResponse(
        leaderboard_event_id=lb_event_id,
        leaderboard_event_window_id=lb_window_id,
        page=page,
        source_updated_at=source_updated_at,
        entries=entries,
    )
    return JSONResponse(status_code=200, content=body.model_dump(by_alias=True, mode="json"))
