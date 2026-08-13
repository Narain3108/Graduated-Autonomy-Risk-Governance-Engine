"""Async SQLAlchemy engine and session factory for SQLite (aiosqlite).

Usage:
    async with get_async_session() as session:
        ...
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from autonomy_guard.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True,
    # SQLite-specific: allow same connection across async tasks in tests.
    connect_args={"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {},
)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields a scoped async session and closes it after use."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Create all tables on application startup."""
    from autonomy_guard.db.models import Base  # noqa: WPS433 — deferred import to avoid circular ref.

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def dispose_engine() -> None:
    """Cleanly dispose the engine on application shutdown."""
    await engine.dispose()
