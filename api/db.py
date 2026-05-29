import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

_engine = None
_SessionLocal = None


def _get_session_factory():
    global _engine, _SessionLocal
    if _SessionLocal is None:
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            raise RuntimeError(
                "DATABASE_URL environment variable is required to start the API."
            )
        _engine = create_async_engine(
            database_url,
            pool_pre_ping=True,   # detect connections dropped by the Supabase pooler
            pool_recycle=1800,    # recycle connections every 30 min
            pool_size=10,
            max_overflow=20,
        )
        _SessionLocal = async_sessionmaker(_engine, expire_on_commit=False)
    return _SessionLocal


def get_engine():
    _get_session_factory()
    return _engine


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    factory = _get_session_factory()
    async with factory() as session:
        yield session
