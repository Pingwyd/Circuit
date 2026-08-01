from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db, get_osirion_client
from app.observability import (
    count_live_main_windows,
    count_snapshots_last_hour,
    merge_rate_limit_stats,
)
from app.osirion.client import OsirionClient
from app.scheduler import get_scheduler

router = APIRouter(prefix="/admin", tags=["admin"])


class RateLimitBucket(BaseModel):
    count: int
    ceiling: int
    utilization: float


class AdminMetricsResponse(BaseModel):
    live_main_windows: int = Field(serialization_alias="liveMainWindows")
    snapshots_last_hour: int = Field(serialization_alias="snapshotsLastHour")
    rate_limits: dict[str, RateLimitBucket] = Field(serialization_alias="rateLimits")
    last_tournament_sync: datetime | None = Field(serialization_alias="lastTournamentSync")


@router.get("/metrics", response_model=AdminMetricsResponse, response_model_by_alias=True)
async def admin_metrics(
    session: AsyncSession = Depends(get_db),
    api_client: OsirionClient = Depends(get_osirion_client),
) -> AdminMetricsResponse:
    scheduler = get_scheduler()
    clients = [scheduler.client]
    if api_client is not scheduler.client:
        clients.append(api_client)

    rate_stats = merge_rate_limit_stats(*clients)
    return AdminMetricsResponse(
        live_main_windows=await count_live_main_windows(session),
        snapshots_last_hour=await count_snapshots_last_hour(session),
        rate_limits={
            bucket: RateLimitBucket(**stats)  # type: ignore[arg-type]
            for bucket, stats in rate_stats.items()
        },
        last_tournament_sync=scheduler.last_tournament_sync,
    )
