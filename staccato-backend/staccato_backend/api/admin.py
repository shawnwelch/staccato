"""Internal ops endpoints consumed by staccato-admin (Bearer ADMIN_API_TOKEN).

The Procrastinate job tables are just Postgres — queried directly here for
the dashboard rather than through a separate broker API.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from staccato_backend.auth import require_admin
from staccato_backend.db import get_session
from staccato_backend.engine import ENGINE_VERSION
from staccato_backend.jobs import QUEUE_BATCH
from staccato_backend.jobs.tasks import analyze_url, classify_channel
from staccato_backend.models import (
    Analysis,
    AnalysisSource,
    AnalysisStatus,
    Channel,
    LiveSession,
    Video,
)
from staccato_backend.providers import get_provider

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])

_PROCRASTINATE_TABLE_SQL = text(
    """
    SELECT id, queue_name, task_name, status, priority, attempts, scheduled_at, args
    FROM procrastinate_jobs
    WHERE (:status IS NULL OR status = :status)
      AND (:queue IS NULL OR queue_name = :queue)
      AND (:task IS NULL OR task_name = :task)
    ORDER BY id DESC
    LIMIT :limit OFFSET :offset
    """
)


@router.get("/jobs")
async def list_jobs(
    status: str | None = None,
    queue: str | None = None,
    task: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        rows = (
            await session.execute(
                _PROCRASTINATE_TABLE_SQL,
                {
                    "status": status,
                    "queue": queue,
                    "task": task,
                    "limit": page_size,
                    "offset": (page - 1) * page_size,
                },
            )
        ).mappings().all()
        count = await session.scalar(
            text(
                "SELECT count(*) FROM procrastinate_jobs "
                "WHERE (:status IS NULL OR status = :status) "
                "AND (:queue IS NULL OR queue_name = :queue) "
                "AND (:task IS NULL OR task_name = :task)"
            ),
            {"status": status, "queue": queue, "task": task},
        )
    except Exception as exc:  # table absent outside Postgres deployments
        raise HTTPException(status_code=503, detail=f"job tables unavailable: {exc}") from exc
    return {
        "items": [dict(r) for r in rows],
        "page": page,
        "page_size": page_size,
        "total": count or 0,
    }


@router.get("/jobs/stats")
async def job_stats(session: AsyncSession = Depends(get_session)) -> dict:
    try:
        by_status = (
            await session.execute(
                text("SELECT status, count(*) AS c FROM procrastinate_jobs GROUP BY status")
            )
        ).all()
        by_queue = (
            await session.execute(
                text("SELECT queue_name, count(*) AS c FROM procrastinate_jobs GROUP BY queue_name")
            )
        ).all()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"job tables unavailable: {exc}") from exc
    return {
        "by_status": {row[0]: row[1] for row in by_status},
        "by_queue": {row[0]: row[1] for row in by_queue},
    }


@router.post("/jobs/{job_id}/retry")
async def retry_job(job_id: int, session: AsyncSession = Depends(get_session)) -> dict:
    """Re-enqueue a failed job by resetting it to todo (Procrastinate semantics)."""
    try:
        result = await session.execute(
            text(
                "UPDATE procrastinate_jobs SET status = 'todo', scheduled_at = now() "
                "WHERE id = :id AND status = 'failed' RETURNING id"
            ),
            {"id": job_id},
        )
        row = result.first()
        await session.commit()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"job tables unavailable: {exc}") from exc
    if row is None:
        raise HTTPException(status_code=404, detail="no failed job with that id")
    return {"ok": True, "job_id": job_id}


class ClassifyRequest(BaseModel):
    channel_url: str
    n_videos: int = Field(default=20, ge=1, le=100)


@router.post("/channels/classify")
async def launch_classification(
    body: ClassifyRequest, session: AsyncSession = Depends(get_session)
) -> dict:
    provider = get_provider("youtube")
    channel_ref = provider.normalize_channel_url(body.channel_url)
    if channel_ref is None:
        raise HTTPException(status_code=422, detail="unrecognized channel URL")
    channel = await session.scalar(
        select(Channel).where(
            Channel.provider == "youtube", Channel.provider_channel_id == channel_ref
        )
    )
    if channel is None:
        channel = Channel(provider="youtube", provider_channel_id=channel_ref)
        session.add(channel)
        await session.commit()
    job_id = await classify_channel.configure(queue=QUEUE_BATCH).defer_async(
        channel_id=channel.id, n_videos=body.n_videos
    )
    return {"channel_id": channel.id, "job_id": job_id}


@router.get("/live-sessions")
async def list_live_sessions(
    promoted: bool | None = None,
    reviewed: bool | None = False,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> dict:
    query = select(LiveSession).order_by(LiveSession.created_at.desc())
    count_query = select(func.count(LiveSession.id))
    if promoted is not None:
        query = query.where(LiveSession.promoted == promoted)
        count_query = count_query.where(LiveSession.promoted == promoted)
    if reviewed is not None:
        query = query.where(LiveSession.reviewed == reviewed)
        count_query = count_query.where(LiveSession.reviewed == reviewed)
    rows = (
        await session.scalars(query.limit(page_size).offset((page - 1) * page_size))
    ).all()
    total = await session.scalar(count_query)
    return {
        "items": [
            {
                "id": s.id,
                "user_id": s.user_id,
                "content_label": s.content_label,
                "duration_s": s.duration_s,
                "cut_count": s.cut_count,
                "device_score": s.device_score,
                "recomputed_score": s.recomputed_score,
                "label": s.label,
                "promoted": s.promoted,
                "reviewed": s.reviewed,
                "created_at": s.created_at.isoformat(),
            }
            for s in rows
        ],
        "page": page,
        "page_size": page_size,
        "total": total or 0,
    }


@router.post("/live-sessions/{session_id}/promote")
async def promote_live_session(
    session_id: str, session: AsyncSession = Depends(get_session)
) -> dict:
    record = await session.get(LiveSession, session_id)
    if record is None:
        raise HTTPException(status_code=404, detail="live session not found")
    record.promoted = True
    record.reviewed = True
    await session.commit()
    return {"ok": True}


@router.post("/live-sessions/{session_id}/reject")
async def reject_live_session(
    session_id: str, session: AsyncSession = Depends(get_session)
) -> dict:
    record = await session.get(LiveSession, session_id)
    if record is None:
        raise HTTPException(status_code=404, detail="live session not found")
    record.promoted = False
    record.reviewed = True
    await session.commit()
    return {"ok": True}


@router.get("/engine/info")
async def engine_info(session: AsyncSession = Depends(get_session)) -> dict:
    rows = (
        await session.execute(
            select(
                Analysis.engine_version,
                func.count(Analysis.id),
                func.avg(Analysis.score),
            )
            .where(Analysis.status == AnalysisStatus.complete)
            .group_by(Analysis.engine_version)
        )
    ).all()
    return {
        "current_version": ENGINE_VERSION,
        "distributions": [
            {
                "engine_version": version,
                "count": count,
                "mean_score": float(mean) if mean is not None else None,
                "median_score": None,  # cheap aggregate only; full dist via rescore dry-run
            }
            for version, count, mean in rows
        ],
    }


class RescoreRequest(BaseModel):
    from_engine_version: str
    dry_run: bool = True


@router.post("/rescore")
async def rescore(body: RescoreRequest, session: AsyncSession = Depends(get_session)) -> dict:
    """Engine-version rollout: enqueue fresh analyses for videos whose latest
    complete analysis is on an older engine version. Old rows are never
    overwritten — scores are versioned, not silently rescored."""
    if body.from_engine_version == ENGINE_VERSION:
        raise HTTPException(status_code=422, detail="that IS the current engine version")
    # One set-based query instead of a per-video lookup: videos whose latest
    # complete analysis is on the old version AND that have no current-version
    # analysis (complete or in flight).
    current = select(Analysis.id).where(
        Analysis.video_id == Video.id,
        Analysis.engine_version == ENGINE_VERSION,
        Analysis.status.in_(
            [AnalysisStatus.complete, AnalysisStatus.queued, AnalysisStatus.running]
        ),
    )
    to_enqueue = (
        await session.scalars(
            select(Video.id)
            .join(Analysis, Analysis.video_id == Video.id)
            .where(
                Analysis.status == AnalysisStatus.complete,
                Analysis.engine_version == body.from_engine_version,
                ~current.exists(),
            )
            .distinct()
        )
    ).all()
    if body.dry_run:
        return {"enqueued": 0, "would_enqueue": len(to_enqueue), "dry_run": True}
    analyses = [
        Analysis(
            video_id=video_id,
            status=AnalysisStatus.queued,
            source=AnalysisSource.url,
            engine_version=ENGINE_VERSION,
        )
        for video_id in to_enqueue
    ]
    session.add_all(analyses)
    await session.commit()
    for analysis in analyses:
        await analyze_url.configure(queue=QUEUE_BATCH).defer_async(analysis_id=analysis.id)
    return {"enqueued": len(analyses), "dry_run": False}
