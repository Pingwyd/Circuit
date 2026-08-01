from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api_schemas import (
    EventWindowDetail,
    ScoreLocationItem,
    TournamentDetailResponse,
    TournamentListItem,
    TournamentListResponse,
)
from app.deps import get_db
from app.models import EventWindow, Tournament

router = APIRouter(prefix="/tournaments", tags=["tournaments"])


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@router.get("", response_model=TournamentListResponse)
async def list_tournaments(
    region: str | None = Query(default=None),
    live: bool | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> TournamentListResponse:
    now = _utc_now()
    live_subq = (
        select(EventWindow.event_window_id)
        .where(
            EventWindow.event_id == Tournament.event_id,
            EventWindow.begin_time <= now,
            EventWindow.end_time >= now,
        )
        .correlate(Tournament)
    )

    stmt = select(Tournament, exists(live_subq).label("is_live"))
    if region:
        stmt = stmt.where(Tournament.regions.contains([region]))
    if live is True:
        stmt = stmt.where(exists(live_subq))
    elif live is False:
        stmt = stmt.where(~exists(live_subq))
    stmt = stmt.order_by(Tournament.last_seen.desc())

    rows = (await db.execute(stmt)).all()
    items = [
        TournamentListItem(
            event_id=tournament.event_id,
            event_group=tournament.event_group,
            regions=tournament.regions,
            platforms=tournament.platforms,
            display_data=tournament.display_data,
            is_live=is_live,
            last_seen=tournament.last_seen,
        )
        for tournament, is_live in rows
    ]
    return TournamentListResponse(tournaments=items)


@router.get("/{event_id}", response_model=TournamentDetailResponse)
async def get_tournament(
    event_id: str,
    db: AsyncSession = Depends(get_db),
) -> TournamentDetailResponse:
    now = _utc_now()
    stmt = (
        select(Tournament)
        .where(Tournament.event_id == event_id)
        .options(
            selectinload(Tournament.event_windows).selectinload(EventWindow.score_locations),
        )
    )
    tournament = (await db.execute(stmt)).scalar_one_or_none()
    if tournament is None:
        raise HTTPException(status_code=404, detail="Tournament not found")

    windows = [
        EventWindowDetail(
            event_window_id=window.event_window_id,
            round=window.round,
            begin_time=window.begin_time,
            end_time=window.end_time,
            is_live=window.begin_time <= now <= window.end_time,
            playlist_id=window.playlist_id,
            match_cap=window.match_cap,
            score_locations=[
                ScoreLocationItem(
                    leaderboard_event_id=sl.leaderboard_event_id,
                    leaderboard_event_window_id=sl.leaderboard_event_window_id,
                    is_main=sl.is_main,
                )
                for sl in window.score_locations
            ],
        )
        for window in sorted(tournament.event_windows, key=lambda w: w.begin_time)
    ]

    return TournamentDetailResponse(
        event_id=tournament.event_id,
        event_group=tournament.event_group,
        regions=tournament.regions,
        platforms=tournament.platforms,
        display_data=tournament.display_data,
        metadata=tournament.metadata_,
        event_windows=windows,
    )
