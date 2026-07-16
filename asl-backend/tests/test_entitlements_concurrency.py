"""The free-tier counter must be race-proof: two simultaneous requests can
never both consume the 3rd (last) free credit.

The real row-lock race runs against Postgres (set ASL_TEST_PG_DSN, e.g.
postgresql+asyncpg://localhost/asl_test — CI does this); the SQLite variant
covers the sequential accounting logic on every run.
"""

from __future__ import annotations

import asyncio
import os

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import asl_backend.db as db_module
from asl_backend.deps.entitlements import QuotaExhausted, consume_free_analysis
from asl_backend.models import Base, UsageCounter, User

PG_DSN = os.environ.get("ASL_TEST_PG_DSN")


async def test_sequential_quota_accounting(engine):
    sessionmaker = db_module.get_sessionmaker()
    async with sessionmaker() as session:
        session.add(User(clerk_user_id="u1"))
        await session.commit()

    for expected_remaining in (2, 1, 0):
        async with sessionmaker() as session:
            remaining = await consume_free_analysis(session, "u1")
            await session.commit()
            assert remaining == expected_remaining

    async with sessionmaker() as session:
        with pytest.raises(QuotaExhausted):
            await consume_free_analysis(session, "u1")


async def test_rollback_returns_credit(engine):
    """If the analysis row fails to land, the credit consumption rolls back too."""
    sessionmaker = db_module.get_sessionmaker()
    async with sessionmaker() as session:
        session.add(User(clerk_user_id="u2"))
        await session.commit()

    async with sessionmaker() as session:
        await consume_free_analysis(session, "u2")
        await session.rollback()

    async with sessionmaker() as session:
        counter = await session.get(UsageCounter, "u2")
        assert counter is None or counter.free_analyses_used == 0


@pytest.mark.skipif(not PG_DSN, reason="ASL_TEST_PG_DSN not set (Postgres required for row-lock race)")
async def test_concurrent_submits_cannot_both_take_last_credit():
    engine = create_async_engine(PG_DSN)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with sessionmaker() as session:
        session.add(User(clerk_user_id="racer"))
        await session.flush()  # no relationship() between the mappers → order manually
        session.add(UsageCounter(user_id="racer", free_analyses_used=2))  # one credit left
        await session.commit()

    barrier = asyncio.Barrier(2)

    async def attempt() -> bool:
        async with sessionmaker() as session:
            await barrier.wait()
            try:
                await consume_free_analysis(session, "racer")
                # Hold the transaction open briefly so the attempts overlap,
                # then commit — the loser must block on the row lock and see
                # the incremented counter.
                await asyncio.sleep(0.2)
                await session.commit()
                return True
            except QuotaExhausted:
                await session.rollback()
                return False

    results = await asyncio.gather(attempt(), attempt())
    assert sorted(results) == [False, True], f"exactly one attempt may win, got {results}"

    async with sessionmaker() as session:
        counter = await session.get(UsageCounter, "racer")
        assert counter.free_analyses_used == 3
    await engine.dispose()
