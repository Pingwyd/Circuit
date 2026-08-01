from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import async_session
from app.osirion.client import OsirionClient

_osirion_client: OsirionClient | None = None


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session


def get_osirion_client() -> OsirionClient:
    global _osirion_client
    if _osirion_client is None:
        _osirion_client = OsirionClient()
    return _osirion_client


async def close_osirion_client() -> None:
    global _osirion_client
    if _osirion_client is not None:
        await _osirion_client.aclose()
        _osirion_client = None
