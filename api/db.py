import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

_engine = None
_SessionLocal = None


def _get_session_factory():
    global _engine, _SessionLocal
    if _SessionLocal is None:
        _engine = create_async_engine(os.environ["DATABASE_URL"])
        _SessionLocal = async_sessionmaker(_engine, expire_on_commit=False)
    return _SessionLocal


def get_engine():
    _get_session_factory()
    return _engine


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    factory = _get_session_factory()
    async with factory() as session:
        yield session
