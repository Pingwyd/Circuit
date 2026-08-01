import asyncio
import logging
import sys
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert

from app.db import async_session
from app.models import (
    EventWindow,
    LeaderboardCurrent,
    LeaderboardEntryPlayer,
    LeaderboardSnapshot,
    Player,
    ScoreLocation,
    Tournament,
)
from app.osirion.client import OsirionClient
from app.schemas import (
    ALL_TOURNAMENT_REGIONS,
    TournamentLeaderboardDataResponse,
    TournamentLeaderboardEntry,
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


@dataclass(frozen=True)
class PollResult:
    snapshot_inserted: bool
    entries_on_page: int
    current_upserted: int
    players_upserted: int
    entry_players_upserted: int
    source_updated_at: datetime
    total_pages: int


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


async def _insert_snapshot(
    session,
    *,
    lb_event_id: str,
    lb_window_id: str,
    page: int,
    total_pages: int,
    source_updated_at: datetime,
    entries: list,
) -> bool:
    stmt = (
        insert(LeaderboardSnapshot)
        .values(
            leaderboard_event_id=lb_event_id,
            leaderboard_event_window_id=lb_window_id,
            page=page,
            total_pages=total_pages,
            source_updated_at=source_updated_at,
            entries=entries,
        )
        .on_conflict_do_nothing(constraint="uq_leaderboard_snapshots_dedupe")
    )
    result = await session.execute(stmt)
    return result.rowcount == 1


async def _upsert_current_row(
    session,
    *,
    lb_event_id: str,
    lb_window_id: str,
    entry: TournamentLeaderboardEntry,
    source_updated_at: datetime,
) -> None:
    stmt = insert(LeaderboardCurrent).values(
        leaderboard_event_id=lb_event_id,
        leaderboard_event_window_id=lb_window_id,
        team_id=entry.team_id,
        rank=entry.rank,
        score=Decimal(str(entry.score)),
        points_earned=Decimal(str(entry.points_earned)),
        percentile=Decimal(str(entry.percentile)),
        players=[p.model_dump(mode="json", by_alias=True) for p in entry.players],
        session_history=_json_list(entry.session_history),
        source_updated_at=source_updated_at,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[
            LeaderboardCurrent.leaderboard_event_id,
            LeaderboardCurrent.leaderboard_event_window_id,
            LeaderboardCurrent.team_id,
        ],
        set_={
            "rank": stmt.excluded.rank,
            "score": stmt.excluded.score,
            "points_earned": stmt.excluded.points_earned,
            "percentile": stmt.excluded.percentile,
            "players": stmt.excluded.players,
            "session_history": stmt.excluded.session_history,
            "source_updated_at": stmt.excluded.source_updated_at,
        },
    )
    await session.execute(stmt)


async def _upsert_player(session, player) -> None:
    now = func.now()
    stmt = insert(Player).values(
        account_id=player.account_id,
        username=player.username,
        flag_token=player.flag_token,
        updated_at=now,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[Player.account_id],
        set_={
            "username": stmt.excluded.username,
            "flag_token": stmt.excluded.flag_token,
            "updated_at": now,
        },
    )
    await session.execute(stmt)


async def _upsert_entry_player(
    session,
    *,
    lb_event_id: str,
    lb_window_id: str,
    team_id: str,
    account_id: str,
    rank: int,
) -> None:
    stmt = insert(LeaderboardEntryPlayer).values(
        leaderboard_event_id=lb_event_id,
        leaderboard_event_window_id=lb_window_id,
        team_id=team_id,
        account_id=account_id,
        rank=rank,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[
            LeaderboardEntryPlayer.leaderboard_event_id,
            LeaderboardEntryPlayer.leaderboard_event_window_id,
            LeaderboardEntryPlayer.account_id,
        ],
        set_={
            "team_id": stmt.excluded.team_id,
            "rank": stmt.excluded.rank,
        },
    )
    await session.execute(stmt)


async def _write_leaderboard_page(
    session,
    *,
    lb_event_id: str,
    lb_window_id: str,
    page: int,
    total_pages: int,
    source_updated_at: datetime,
    entries: list[TournamentLeaderboardEntry],
) -> PollResult:
    entries_json = [entry.model_dump(mode="json", by_alias=True) for entry in entries]
    snapshot_inserted = await _insert_snapshot(
        session,
        lb_event_id=lb_event_id,
        lb_window_id=lb_window_id,
        page=page,
        total_pages=total_pages,
        source_updated_at=source_updated_at,
        entries=entries_json,
    )

    current_upserted = 0
    players_upserted = 0
    entry_players_upserted = 0

    for entry in entries:
        await _upsert_current_row(
            session,
            lb_event_id=lb_event_id,
            lb_window_id=lb_window_id,
            entry=entry,
            source_updated_at=source_updated_at,
        )
        current_upserted += 1
        for player in entry.players:
            await _upsert_player(session, player)
            players_upserted += 1
            await _upsert_entry_player(
                session,
                lb_event_id=lb_event_id,
                lb_window_id=lb_window_id,
                team_id=entry.team_id,
                account_id=player.account_id,
                rank=entry.rank,
            )
            entry_players_upserted += 1

    return PollResult(
        snapshot_inserted=snapshot_inserted,
        entries_on_page=len(entries),
        current_upserted=current_upserted,
        players_upserted=players_upserted,
        entry_players_upserted=entry_players_upserted,
        source_updated_at=source_updated_at,
        total_pages=total_pages,
    )


async def poll_leaderboard(
    lb_event_id: str,
    lb_window_id: str,
    page: int = 0,
    client: OsirionClient | None = None,
) -> PollResult:
    owns_client = client is None
    if owns_client:
        client = OsirionClient()

    try:
        raw = await client.get_leaderboard(lb_event_id, lb_window_id, page=page)
        parsed = TournamentLeaderboardDataResponse.model_validate(raw)
        if not parsed.success:
            raise ValueError("Osirion leaderboard call returned success=false")

        lb = parsed.leaderboard
        async with async_session() as session:
            async with session.begin():
                return await _write_leaderboard_page(
                    session,
                    lb_event_id=lb.leaderboard_event_id,
                    lb_window_id=lb.leaderboard_event_window_id,
                    page=lb.page,
                    total_pages=lb.total_pages,
                    source_updated_at=lb.updated_at,
                    entries=lb.entries,
                )
    finally:
        if owns_client:
            await client.aclose()


async def _main() -> None:
    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) >= 2 and sys.argv[1] == "poll":
        if len(sys.argv) < 4:
            raise SystemExit("Usage: python -m app.osirion.ingest poll LB_EVENT_ID LB_WINDOW_ID [PAGE]")
        lb_event_id = sys.argv[2]
        lb_window_id = sys.argv[3]
        page = int(sys.argv[4]) if len(sys.argv) > 4 else 0
        result = await poll_leaderboard(lb_event_id, lb_window_id, page=page)
        logger.info(
            "Poll complete: snapshot_inserted=%s entries=%d current=%d players=%d entry_players=%d updated_at=%s total_pages=%d",
            result.snapshot_inserted,
            result.entries_on_page,
            result.current_upserted,
            result.players_upserted,
            result.entry_players_upserted,
            result.source_updated_at.isoformat(),
            result.total_pages,
        )
        return

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
