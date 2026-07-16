from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from asl_backend.api.serializers import analysis_out, video_out
from asl_backend.auth import Identity, require_identity
from asl_backend.db import get_session
from asl_backend.deps.entitlements import (
    EntitlementInfo,
    consume_free_analysis,
    get_entitlement,
)
from asl_backend.engine import ENGINE_VERSION
from asl_backend.jobs import QUEUE_INTERACTIVE
from asl_backend.jobs.tasks import analyze_url
from asl_backend.models import Analysis, AnalysisSource, AnalysisStatus, SharePage, Video
from asl_backend.providers import normalize_any_url
from asl_backend.schemas import (
    AnalysisCreateRequest,
    AnalysisCreateResponse,
    AnalysisStatusResponse,
    EntitlementOut,
)

router = APIRouter(prefix="/v1/analyses", tags=["analyses"])


def _entitlement_out(e: EntitlementInfo, consumed: bool = False) -> EntitlementOut:
    used = e.free_analyses_used + (1 if consumed and not e.is_pro else 0)
    return EntitlementOut(
        plan=e.plan,
        source=e.source,
        status=e.status,
        free_analyses_used=used,
        free_analyses_limit=e.free_analyses_limit,
        free_remaining=max(0, e.free_analyses_limit - used),
    )


def _set_quota_header(response: Response, entitlement_out: EntitlementOut) -> None:
    # iOS renders the remaining free-scan count from this header; pros get -1
    # ("unlimited") so the client never shows a counter.
    remaining = -1 if entitlement_out.plan == "pro" else entitlement_out.free_remaining
    response.headers["X-Scans-Remaining"] = str(remaining)


@router.post("", status_code=202, response_model=AnalysisCreateResponse)
async def create_analysis(
    body: AnalysisCreateRequest,
    response: Response,
    identity: Identity = Depends(require_identity),
    entitlement: EntitlementInfo = Depends(get_entitlement),
    session: AsyncSession = Depends(get_session),
) -> AnalysisCreateResponse:
    normalized = normalize_any_url(body.url)
    if normalized is None:
        raise HTTPException(status_code=422, detail="unsupported or unrecognized video URL")

    video = await session.scalar(
        select(Video).where(
            Video.provider == normalized.provider,
            Video.provider_video_id == normalized.provider_video_id,
        )
    )

    # Dedupe BEFORE entitlement consumption: a completed analysis for the same
    # video at the current engine version is returned instantly and never
    # burns a free credit.
    if video is not None:
        existing = await session.scalar(
            select(Analysis)
            .where(
                Analysis.video_id == video.id,
                Analysis.status == AnalysisStatus.complete,
                Analysis.engine_version == ENGINE_VERSION,
            )
            .order_by(Analysis.completed_at.desc())
        )
        if existing is not None:
            share = await session.scalar(
                select(SharePage).where(SharePage.analysis_id == existing.id)
            )
            ent_out = _entitlement_out(entitlement)
            _set_quota_header(response, ent_out)
            return AnalysisCreateResponse(
                analysis=analysis_out(existing),
                video=video_out(video),
                share_slug=share.slug if share else None,
                deduped=True,
                entitlement=ent_out,
            )

    # Consume a free credit (row-locked) unless pro; same transaction as the
    # analysis row so a failure rolls both back.
    if not entitlement.is_pro:
        await consume_free_analysis(session, identity.user_id)

    if video is None:
        video = Video(
            provider=normalized.provider,
            provider_video_id=normalized.provider_video_id,
        )
        session.add(video)
        await session.flush()

    analysis = Analysis(
        video_id=video.id,
        requested_by=identity.user_id,
        status=AnalysisStatus.queued,
        source=AnalysisSource.url,
        engine_version=ENGINE_VERSION,
        input_url=normalized.canonical_url,
    )
    session.add(analysis)
    await session.commit()

    # Enqueue after commit; if the defer itself fails, mark the row failed so
    # the client isn't left polling a job that never existed. (Admin retry can
    # also re-enqueue stuck rows.)
    try:
        await analyze_url.configure(queue=QUEUE_INTERACTIVE).defer_async(analysis_id=analysis.id)
    except Exception:
        analysis.status = AnalysisStatus.failed
        analysis.error = "failed to enqueue analysis job"
        await session.commit()
        raise HTTPException(status_code=503, detail="queue unavailable, try again")

    ent_out = _entitlement_out(entitlement, consumed=True)
    _set_quota_header(response, ent_out)
    return AnalysisCreateResponse(
        analysis=analysis_out(analysis),
        video=video_out(video),
        share_slug=None,
        deduped=False,
        entitlement=ent_out,
    )


@router.get("/{analysis_id}", response_model=AnalysisStatusResponse)
async def get_analysis(
    analysis_id: str,
    identity: Identity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
) -> AnalysisStatusResponse:
    analysis = await session.get(Analysis, analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="analysis not found")
    # Completed analyses are public data (they're served on share pages and
    # returned to other users via dedupe). In-flight and failed rows are only
    # visible to whoever requested them — 404, not 403, so ids don't leak.
    if analysis.status != AnalysisStatus.complete and analysis.requested_by != identity.user_id:
        raise HTTPException(status_code=404, detail="analysis not found")
    video = await session.get(Video, analysis.video_id) if analysis.video_id else None
    share = await session.scalar(select(SharePage).where(SharePage.analysis_id == analysis.id))
    return AnalysisStatusResponse(
        analysis=analysis_out(analysis),
        video=video_out(video),
        share_slug=share.slug if share else None,
    )
