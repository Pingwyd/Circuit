from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api_schemas import (
    PlayerPlacementItem,
    PlayerPlacementsResponse,
    PlayerSearchItem,
    PlayerSearchResponse,
)
from app.deps import get_db, get_osirion_client
from app.models import LeaderboardEntryPlayer, Player
from app.osirion.client import OsirionClient

router = APIRouter(prefix="/players", tags=["players"])


@router.get("/search", response_model=PlayerSearchResponse)
async def search_players(
    name: str = Query(min_length=1),
    db: AsyncSession = Depends(get_db),
    client: OsirionClient = Depends(get_osirion_client),
) -> PlayerSearchResponse:
    pattern = f"{name.lower()}%"
    rows = (
        await db.execute(
            select(Player)
            .where(func.lower(Player.username).like(pattern))
            .order_by(Player.username)
            .limit(20)
        )
    ).scalars().all()

    if rows:
        return PlayerSearchResponse(
            source="database",
            players=[
                PlayerSearchItem(
                    account_id=row.account_id,
                    username=row.username,
                    flag_token=row.flag_token,
                )
                for row in rows
            ],
        )

    raw = await client.lookup_by_name(name)
    if not raw.get("success"):
        return PlayerSearchResponse(source="lookup", players=[])

    data = raw.get("data") or raw
    account_id = data.get("accountId") or data.get("id")
    if not account_id:
        return PlayerSearchResponse(source="lookup", players=[])

    return PlayerSearchResponse(
        source="lookup",
        players=[
            PlayerSearchItem(
                account_id=account_id,
                username=data.get("displayName") or data.get("username"),
                flag_token=data.get("flagToken"),
            )
        ],
    )


@router.get("/{account_id}/placements", response_model=PlayerPlacementsResponse)
async def get_player_placements(
    account_id: str,
    db: AsyncSession = Depends(get_db),
) -> PlayerPlacementsResponse:
    rows = (
        await db.execute(
            select(LeaderboardEntryPlayer)
            .where(LeaderboardEntryPlayer.account_id == account_id)
            .order_by(LeaderboardEntryPlayer.rank)
        )
    ).scalars().all()

    if not rows:
        raise HTTPException(status_code=404, detail="No placements found for account")

    return PlayerPlacementsResponse(
        account_id=account_id,
        placements=[
            PlayerPlacementItem(
                leaderboard_event_id=row.leaderboard_event_id,
                leaderboard_event_window_id=row.leaderboard_event_window_id,
                team_id=row.team_id,
                rank=row.rank,
            )
            for row in rows
        ],
    )
