from __future__ import annotations

import os
import tempfile

os.environ.setdefault("STACCATO_ENV", "test")
os.environ.setdefault("STACCATO_AUTH_MODE", "dev")
os.environ.setdefault("STACCATO_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("STACCATO_STORAGE_BACKEND", "local")
os.environ.setdefault("STACCATO_MEDIA_ROOT", tempfile.mkdtemp(prefix="staccato-media-"))
os.environ.setdefault("STACCATO_APPLE_VERIFY_SIGNATURES", "false")

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import staccato_backend.db as db_module
from staccato_backend.jobs import app as procrastinate_app
from staccato_backend.models import Base


@pytest_asyncio.fixture()
async def engine():
    """Fresh in-memory SQLite per test (StaticPool → one shared connection)."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    db_module._engine = engine
    db_module._sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    yield engine
    await engine.dispose()
    db_module.reset_engine()


@pytest_asyncio.fixture()
async def client(engine):
    from staccato_backend.main import create_app

    app = create_app()
    # Bypass lifespan (it would re-create tables on the global engine and open
    # procrastinate); tables already exist on the fixture engine.
    procrastinate_app.connector.reset()
    transport = ASGITransport(app=app)
    async with procrastinate_app.open_async():
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


@pytest.fixture()
def auth_headers():
    return {"Authorization": "Bearer dev:user_test_1"}


@pytest.fixture()
def admin_headers():
    return {"Authorization": "Bearer dev-admin-token"}
