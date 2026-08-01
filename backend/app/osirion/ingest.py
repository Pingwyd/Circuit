import asyncio
import logging
from dataclasses import dataclass

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert

from app.db import async_session
from app.models import EventWindow, ScoreLocation, Tournament
from app.osirion.client import OsirionClient
from app.schemas import (
    ALL_TOURNAMENT_REGIONS,
    TournamentsDataResponse,
    TournamentsDataScoreLocation,
    TournamentsDataTournament,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SyncCounts:
    tournaments: int
    event_windows: int
    score_locations: int
    regions_fetched: int


def _json_list(items: list) -> list:
    return [item.model_dump(mode="json", by_alias=True) for item in items]


async def _fetch_all_tournaments(client: OsirionClient) -> dict[str, TournamentsDataTournament]:
    by_event_id: dict[str, TournamentsDataTournament] = {}
    for region in ALL_TOURNAMENT_REGIONS:
        raw = await client.get_tournaments(region=region, historic=False)
        parsed = TournamentsDataResponse.model_validate(raw)
        if not parsed.success:
            logger.warning("Osirion tournaments call for %s returned success=false", region)
            continue
        for tournament in parsed.tournaments:
            by_event_id[tournament.event_id] = tournament
    return by_event_id


async def _upsert_tournament(session, tournament: TournamentsDataTournament) -> None:
    now = func.now()
    stmt = insert(Tournament).values(
        event_id=tournament.event_id,
        event_group=tournament.event_group,
        regions=tournament.regions,
        platforms=tournament.platforms,
        display_data=tournament.display_data.model_dump(mode="json", by_alias=True),
        metadata_=tournament.metadata,
        last_seen=now,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[Tournament.event_id],
        set_={
            "event_group": stmt.excluded.event_group,
            "regions": stmt.excluded.regions,
            "platforms": stmt.excluded.platforms,
            "display_data": stmt.excluded.display_data,
            "metadata": stmt.excluded.metadata,
            "last_seen": now,
        },
    )
    await session.execute(stmt)


async def _upsert_event_window(session, tournament: TournamentsDataTournament, window) -> None:
    now = func.now()
    stmt = insert(EventWindow).values(
        event_window_id=window.event_window_id,
        event_id=tournament.event_id,
        round=window.round,
        begin_time=window.begin_time,
        end_time=window.end_time,
        playlist_id=window.playlist_id,
        match_cap=window.match_cap,
        require_all_tokens=window.require_all_tokens,
        require_any_tokens=window.require_any_tokens,
        metadata_=window.metadata,
        last_seen=now,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[EventWindow.event_window_id],
        set_={
            "event_id": stmt.excluded.event_id,
            "round": stmt.excluded.round,
            "begin_time": stmt.excluded.begin_time,
            "end_time": stmt.excluded.end_time,
            "playlist_id": stmt.excluded.playlist_id,
            "match_cap": stmt.excluded.match_cap,
            "require_all_tokens": stmt.excluded.require_all_tokens,
            "require_any_tokens": stmt.excluded.require_any_tokens,
            "metadata": stmt.excluded.metadata,
            "last_seen": now,
        },
    )
    await session.execute(stmt)


async def _upsert_score_location(
    session,
    event_window_id: str,
    location: TournamentsDataScoreLocation,
) -> None:
    stmt = insert(ScoreLocation).values(
        event_window_id=event_window_id,
        leaderboard_event_id=location.leaderboard_event_id,
        leaderboard_event_window_id=location.leaderboard_event_window_id,
        is_main=location.is_main,
        payout_tables=_json_list(location.payout_tables),
        scoring_rules=_json_list(location.scoring_rules),
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_score_locations_lb_ids",
        set_={
            "event_window_id": stmt.excluded.event_window_id,
            "is_main": stmt.excluded.is_main,
            "payout_tables": stmt.excluded.payout_tables,
            "scoring_rules": stmt.excluded.scoring_rules,
        },
    )
    await session.execute(stmt)


async def sync_tournaments(client: OsirionClient | None = None) -> SyncCounts:
    owns_client = client is None
    if owns_client:
        client = OsirionClient()

    tournament_count = 0
    window_count = 0
    score_location_count = 0

    try:
        tournaments = await _fetch_all_tournaments(client)
        async with async_session() as session:
            async with session.begin():
                for tournament in tournaments.values():
                    await _upsert_tournament(session, tournament)
                    tournament_count += 1
                    for window in tournament.event_windows:
                        await _upsert_event_window(session, tournament, window)
                        window_count += 1
                        for location in window.score_locations:
                            await _upsert_score_location(session, window.event_window_id, location)
                            score_location_count += 1

        return SyncCounts(
            tournaments=tournament_count,
            event_windows=window_count,
            score_locations=score_location_count,
            regions_fetched=len(ALL_TOURNAMENT_REGIONS),
        )
    finally:
        if owns_client:
            await client.aclose()


async def _main() -> None:
    logging.basicConfig(level=logging.INFO)
    counts = await sync_tournaments()
    logger.info(
        "Sync complete: %d tournaments, %d event windows, %d score locations (%d regions)",
        counts.tournaments,
        counts.event_windows,
        counts.score_locations,
        counts.regions_fetched,
    )


if __name__ == "__main__":
    asyncio.run(_main())
