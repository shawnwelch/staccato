from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from asl_backend.db import get_session
from asl_backend.deps.entitlements import EntitlementInfo, require_pro
from asl_backend.engine.scoring import summarize_cuts
from asl_backend.models import LiveSession
from asl_backend.schemas import LiveSessionCreateRequest, LiveSessionOut

router = APIRouter(prefix="/v1/live-sessions", tags=["live-sessions"])


@router.post("", status_code=201, response_model=LiveSessionOut)
async def create_live_session(
    body: LiveSessionCreateRequest,
    entitlement: EntitlementInfo = Depends(require_pro),
    session: AsyncSession = Depends(get_session),
) -> LiveSessionOut:
    """Accept an optical capture summary (paid tier).

    The score is recomputed server-side from the submitted cut times — client
    math is never trusted for published data. Optical scans stay out of
    canonical title scores until promoted through admin moderation.
    """
    if any(t < 0 or t > body.duration_s for t in body.cut_times_s):
        raise HTTPException(status_code=422, detail="cut times must lie within [0, duration]")
    try:
        summary = summarize_cuts(body.cut_times_s, body.duration_s)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    record = LiveSession(
        user_id=entitlement.user_id,
        content_label=body.content_label or "unknown",
        device_summary_json={
            "cut_times_s": body.cut_times_s,
            "duration_s": body.duration_s,
            "device_score": body.device_score,
        },
        duration_s=body.duration_s,
        cut_count=summary.cut_count,
        device_score=body.device_score,
        recomputed_score=summary.score,
        label=summary.label,
        engine_version=summary.engine_version,
    )
    session.add(record)
    await session.commit()
    return LiveSessionOut(
        id=record.id,
        recomputed_score=summary.score,
        label=summary.label,
        cut_count=summary.cut_count,
        median_shot_s=summary.median_shot_s,
        cuts_per_minute=summary.cuts_per_minute,
        engine_version=summary.engine_version,
        device_score=body.device_score,
        promoted=False,
    )
