"""Entitlement checks live here and only here.

Every gated route depends on `get_entitlement`; free-tier consumption goes
through `consume_free_analysis`, which takes a row lock on the user's usage
counter so two simultaneous submits can't both take the 3rd free slot.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from asl_backend.auth import Identity, require_identity
from asl_backend.config import get_settings
from asl_backend.db import get_session
from asl_backend.models import (
    Entitlement,
    EntitlementStatus,
    UsageCounter,
)


@dataclass(frozen=True)
class EntitlementInfo:
    user_id: str
    plan: Literal["free", "pro"]
    source: str | None  # apple | stripe | promo
    status: str
    current_period_end: datetime | None
    free_analyses_used: int
    free_analyses_limit: int

    @property
    def is_pro(self) -> bool:
        return self.plan == "pro"

    @property
    def free_remaining(self) -> int:
        return max(0, self.free_analyses_limit - self.free_analyses_used)


class QuotaExhausted(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=402,
            detail={
                "code": "free_quota_exhausted",
                "message": "Free analyses used up. Subscribe for unlimited scans.",
                "free_remaining": 0,
            },
            # The iOS client renders the remaining count from this header.
            headers={"X-Scans-Remaining": "0"},
        )


async def _active_entitlement(session: AsyncSession, user_id: str) -> Entitlement | None:
    now = datetime.now(UTC)
    rows = (
        await session.scalars(
            select(Entitlement)
            .where(Entitlement.user_id == user_id)
            .where(Entitlement.status.in_([EntitlementStatus.active, EntitlementStatus.grace]))
            .order_by(Entitlement.updated_at.desc())
        )
    ).all()
    for ent in rows:
        end = ent.current_period_end
        if end is not None and end.tzinfo is None:
            end = end.replace(tzinfo=UTC)
        if end is None or end > now:
            return ent
    return None


async def load_entitlement(session: AsyncSession, user_id: str) -> EntitlementInfo:
    settings = get_settings()
    ent = await _active_entitlement(session, user_id)
    counter = await session.get(UsageCounter, user_id)
    used = counter.free_analyses_used if counter else 0
    if ent is not None:
        return EntitlementInfo(
            user_id=user_id,
            plan="pro",
            source=ent.source.value,
            status=ent.status.value,
            current_period_end=ent.current_period_end,
            free_analyses_used=used,
            free_analyses_limit=settings.free_analyses_limit,
        )
    return EntitlementInfo(
        user_id=user_id,
        plan="free",
        source=None,
        status="none",
        current_period_end=None,
        free_analyses_used=used,
        free_analyses_limit=settings.free_analyses_limit,
    )


async def get_entitlement(
    identity: Identity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> EntitlementInfo:
    return await load_entitlement(session, identity.user_id)


async def consume_free_analysis(session: AsyncSession, user_id: str) -> int:
    """Atomically consume one free analysis; returns remaining after consume.

    SELECT ... FOR UPDATE on the counter row serializes concurrent submits
    (Postgres; SQLite serializes at the connection level anyway). Commit/rollback
    is the caller's responsibility so the analysis row and the counter increment
    land in the same transaction.
    """
    settings = get_settings()
    # Ensure the row exists first (ON CONFLICT DO NOTHING avoids the race where
    # two first-ever requests both try to insert), then lock it.
    dialect = session.bind.dialect.name if session.bind is not None else "sqlite"
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        stmt = pg_insert(UsageCounter).values(user_id=user_id, free_analyses_used=0)
        await session.execute(stmt.on_conflict_do_nothing(index_elements=["user_id"]))
    else:
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        stmt = sqlite_insert(UsageCounter).values(user_id=user_id, free_analyses_used=0)
        await session.execute(stmt.on_conflict_do_nothing(index_elements=["user_id"]))
    counter = await session.scalar(
        select(UsageCounter).where(UsageCounter.user_id == user_id).with_for_update()
    )
    assert counter is not None
    if counter.free_analyses_used >= settings.free_analyses_limit:
        raise QuotaExhausted()
    counter.free_analyses_used += 1
    return settings.free_analyses_limit - counter.free_analyses_used


def require_pro(entitlement: EntitlementInfo = Depends(get_entitlement)) -> EntitlementInfo:
    if not entitlement.is_pro:
        raise HTTPException(
            status_code=402,
            detail={
                "code": "pro_required",
                "message": "This feature requires an active subscription.",
            },
        )
    return entitlement
