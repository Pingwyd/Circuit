import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.db import check_database_connection, engine
from app.deps import close_osirion_client
from app.routers import admin, leaderboards, players, tournaments
from app.scheduler import get_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await check_database_connection()
    scheduler = get_scheduler()
    if settings.scheduler_enabled:
        scheduler.start()
    yield
    if settings.scheduler_enabled:
        await scheduler.stop()
    await close_osirion_client()
    await engine.dispose()


app = FastAPI(title="Tournament Tracker", lifespan=lifespan)

app.include_router(admin.router)
app.include_router(tournaments.router)
app.include_router(leaderboards.router)
app.include_router(players.router)


@app.get("/health")
async def health() -> dict[str, bool]:
    return {"ok": True}
