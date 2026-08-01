import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db import check_database_connection, engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await check_database_connection()
    yield
    await engine.dispose()


app = FastAPI(title="Tournament Tracker", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, bool]:
    return {"ok": True}
