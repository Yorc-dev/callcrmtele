"""Async database engine, session factory, and initialisation helpers."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.db.models import Base

logger = logging.getLogger(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _get_engine(db_url: str) -> AsyncEngine:
    """Return (creating if necessary) the module-level async engine."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            db_url,
            echo=False,
            pool_size=5,
            max_overflow=10,
        )
    return _engine


def _get_session_factory(db_url: str) -> async_sessionmaker[AsyncSession]:
    """Return (creating if necessary) the module-level session factory."""
    global _session_factory
    if _session_factory is None:
        engine = _get_engine(db_url)
        _session_factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


async def init_db(db_url: str) -> None:
    """Create all tables if they do not exist yet.

    Args:
        db_url: Async-compatible PostgreSQL connection URL.
    """
    engine = _get_engine(db_url)
    logger.info("Initialising database schema…")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database schema is ready.")


@asynccontextmanager
async def get_session(db_url: str) -> AsyncGenerator[AsyncSession, None]:
    """Async context manager that yields an :class:`AsyncSession`.

    The session is committed on success and rolled back on exception.

    Args:
        db_url: Async-compatible PostgreSQL connection URL.

    Yields:
        An open :class:`AsyncSession` instance.
    """
    factory = _get_session_factory(db_url)
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
