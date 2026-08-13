"""Pytest fixtures and configuration for AutonomyGuard testing.

Sets up isolated async SQLite test database and httpx AsyncClient.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from autonomy_guard.config import settings
from autonomy_guard.db.models import Base
from autonomy_guard.main import app
from autonomy_guard.api.dependencies import get_db

# Override the database URL for tests to use an in-memory SQLite database
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    future=True,
    connect_args={"check_same_thread": False},
)

TestingSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with TestingSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db() -> AsyncGenerator[None, None]:
    """Create and drop all tables before and after each test."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    yield
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Yield an httpx AsyncClient configured for the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session directly for use in tests."""
    async with TestingSessionLocal() as session:
        yield session
