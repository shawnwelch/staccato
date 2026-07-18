from __future__ import annotations

import asyncio
import json
import logging
import secrets
import tempfile
from pathlib import Path

from sqlalchemy import select

from staccato_backend.config import get_settings
from staccato_backend.db import get_sessionmaker
from staccato_backend.engine import ENGINE_VERSION
from staccato_backend.jobs import QUEUE_BATCH, QUEUE_INTERACTIVE, app
from staccato_backend.jobs.channel_scoring import trend_bucket, trend_slope, view_weighted_score
from staccato_backend.models import (
    Analysis,
    AnalysisSource,
    AnalysisStatus,
    Channel,
    ChannelScore,
    SharePage,
    Trend,
    Video,
    utcnow,
)
from staccato_backend.providers import ChannelVideoRef, NormalizedVideo, get_provider
from staccato_backend.storage import get_storage

logger = logging.getLogger(__name__)

_FINALIZE_MAX_ATTEMPTS = 40
_FINALIZE_RETRY_DELAY_S = 30


def _new_slug() -> str:
    return secrets.token_urlsafe(6)


@app.task(name="analyze_url", queue=QUEUE_INTERACTIVE, retry=2)
async def analyze_url(analysis_id: str) -> None:
    """Fetch → detect → score → store artifacts → mark complete."""
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        analysis = await session.get(Analysis, analysis_id)
        if analysis is None:
            logger.warning("analysis %s vanished", analysis_id)
            return
        if analysis.status == AnalysisStatus.complete:
            return  # idempotent on retry
        video = await session.get(Video, analysis.video_id) if analysis.video_id else None
        if video is None:
            await _fail(session, analysis, "analysis has no video row")
            return
        analysis.status = AnalysisStatus.running
        analysis.started_at = utcnow()
        await session.commit()

        provider = get_provider(video.provider)
        normalized = NormalizedVideo(
            provider=video.provider,
            provider_video_id=video.provider_video_id,
            canonical_url=analysis.input_url
            or f"https://www.youtube.com/watch?v={video.provider_video_id}",
        )
        try:
            # Blocking fetch/decode work stays off the worker's event loop.
            metadata = await asyncio.to_thread(provider.fetch_metadata, normalized)
            video.title = metadata.title or video.title
            video.channel_title = metadata.channel_title or video.channel_title
            video.duration_s = metadata.duration_s or video.duration_s
            video.view_count = metadata.view_count if metadata.view_count is not None else video.view_count
            video.published_at = metadata.published_at or video.published_at
            if metadata.channel_provider_id:
                channel = await session.scalar(
                    select(Channel).where(
                        Channel.provider == video.provider,
                        Channel.provider_channel_id == metadata.channel_provider_id,
                    )
                )
                if channel is None:
                    channel = Channel(
                        provider=video.provider,
                        provider_channel_id=metadata.channel_provider_id,
                        title=metadata.channel_title,
                    )
                    session.add(channel)
                    await session.flush()
                video.channel_id = channel.id
            await session.commit()

            with tempfile.TemporaryDirectory(prefix="staccato-") as tmp:
                path = await asyncio.to_thread(provider.download_lowres, normalized, Path(tmp))
                result = await asyncio.to_thread(_run_engine, path)

            storage = get_storage()
            key_base = f"analyses/{analysis.id}"
            result_url = storage.put(
                f"{key_base}/result.json",
                json.dumps(result).encode(),
                "application/json",
            )
            from staccato_backend.engine.render import render_heatmap_png

            png = render_heatmap_png(
                result["heatmap"]["bin_centers_s"],
                result["heatmap"]["cuts_per_min"],
                result["duration_s"],
            )
            heatmap_url = storage.put(f"{key_base}/heatmap.png", png, "image/png")

            analysis.score = result["score"]
            analysis.label = result["label"]
            analysis.median_shot_s = result["median_shot_s"]
            analysis.cuts_per_minute = result["cuts_per_minute"]
            analysis.cut_count = result["cut_count"]
            analysis.duration_s = result["duration_s"]
            analysis.result_json_url = result_url
            analysis.heatmap_png_url = heatmap_url
            analysis.engine_version = result["engine_version"]
            analysis.status = AnalysisStatus.complete
            analysis.completed_at = utcnow()
            analysis.error = None

            existing_share = await session.scalar(
                select(SharePage).where(SharePage.analysis_id == analysis.id)
            )
            if existing_share is None:
                session.add(SharePage(slug=_new_slug(), analysis_id=analysis.id))
            await session.commit()
        except Exception as exc:  # noqa: BLE001 — job boundary
            logger.exception("analysis %s failed", analysis_id)
            await session.rollback()
            analysis = await session.get(Analysis, analysis_id)
            if analysis is not None:
                await _fail(session, analysis, str(exc)[:2000])
            raise


def _run_engine(path: Path) -> dict:
    from staccato_backend.engine import analyze

    return analyze(path)


async def _fail(session, analysis: Analysis, message: str) -> None:
    analysis.status = AnalysisStatus.failed
    analysis.error = message
    analysis.completed_at = utcnow()
    await session.commit()


@app.task(name="classify_channel", queue=QUEUE_BATCH, retry=1)
async def classify_channel(channel_id: str, n_videos: int | None = None) -> None:
    """Fan out one analyze_url per recent video, then schedule the finalizer."""
    settings = get_settings()
    n = n_videos or settings.channel_scan_default_n
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        channel = await session.get(Channel, channel_id)
        if channel is None:
            logger.warning("channel %s vanished", channel_id)
            return
        provider = get_provider(channel.provider)
        refs: list[ChannelVideoRef] = await asyncio.to_thread(
            provider.list_recent_videos, channel.provider_channel_id, n
        )
        if not refs:
            logger.warning("channel %s: no videos found", channel_id)
            return

        video_ids: list[str] = []
        for ref in refs:
            if settings.batch_queue_throttle_s:
                await asyncio.sleep(settings.batch_queue_throttle_s)
            video = await session.scalar(
                select(Video).where(
                    Video.provider == channel.provider,
                    Video.provider_video_id == ref.provider_video_id,
                )
            )
            if video is None:
                video = Video(
                    provider=channel.provider,
                    provider_video_id=ref.provider_video_id,
                    title=ref.title,
                    channel_id=channel.id,
                    view_count=ref.view_count,
                    published_at=ref.published_at,
                )
                session.add(video)
                await session.flush()
            else:
                video.channel_id = video.channel_id or channel.id
                video.view_count = ref.view_count if ref.view_count is not None else video.view_count
                video.published_at = ref.published_at or video.published_at
            video_ids.append(video.id)

            # Dedupe: an existing complete analysis at the current engine
            # version means no new job.
            existing = await session.scalar(
                select(Analysis).where(
                    Analysis.video_id == video.id,
                    Analysis.status == AnalysisStatus.complete,
                    Analysis.engine_version == ENGINE_VERSION,
                )
            )
            if existing is not None:
                continue
            pending = await session.scalar(
                select(Analysis).where(
                    Analysis.video_id == video.id,
                    Analysis.status.in_([AnalysisStatus.queued, AnalysisStatus.running]),
                )
            )
            if pending is not None:
                continue
            analysis = Analysis(
                video_id=video.id,
                requested_by=None,
                status=AnalysisStatus.queued,
                source=AnalysisSource.url,
                engine_version=ENGINE_VERSION,
                input_url=ref.canonical_url,
            )
            session.add(analysis)
            await session.commit()
            await analyze_url.configure(queue=QUEUE_BATCH).defer_async(analysis_id=analysis.id)
        await session.commit()

    await finalize_channel_score.configure(schedule_in={"seconds": _FINALIZE_RETRY_DELAY_S}).defer_async(
        channel_id=channel_id, video_ids=video_ids, attempt=0
    )


@app.task(name="finalize_channel_score", queue=QUEUE_BATCH)
async def finalize_channel_score(channel_id: str, video_ids: list[str], attempt: int = 0) -> None:
    """Compute the channel score once the fan-out has (mostly) landed.

    Re-schedules itself while analyses are still in flight, then scores over
    whatever completed (videos that failed analysis are dropped from the set).
    """
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        pending = (
            await session.scalars(
                select(Analysis).where(
                    Analysis.video_id.in_(video_ids),
                    Analysis.status.in_([AnalysisStatus.queued, AnalysisStatus.running]),
                )
            )
        ).all()
        if pending and attempt < _FINALIZE_MAX_ATTEMPTS:
            await finalize_channel_score.configure(
                schedule_in={"seconds": _FINALIZE_RETRY_DELAY_S}
            ).defer_async(channel_id=channel_id, video_ids=video_ids, attempt=attempt + 1)
            return

        # Two queries for the whole batch instead of two per video: latest
        # complete current-version analysis per video, plus the video rows.
        analyses = (
            await session.scalars(
                select(Analysis)
                .where(
                    Analysis.video_id.in_(video_ids),
                    Analysis.status == AnalysisStatus.complete,
                    Analysis.engine_version == ENGINE_VERSION,
                )
                .order_by(Analysis.completed_at.desc())
            )
        ).all()
        latest_by_video: dict[str, Analysis] = {}
        for a in analyses:
            if a.video_id not in latest_by_video:
                latest_by_video[a.video_id] = a
        videos = {
            v.id: v
            for v in (await session.scalars(select(Video).where(Video.id.in_(video_ids)))).all()
        }
        series = []
        for video_id in video_ids:
            analysis = latest_by_video.get(video_id)
            if analysis is None or analysis.score is None:
                continue
            video = videos.get(video_id)
            series.append(
                {
                    "provider_video_id": video.provider_video_id if video else video_id,
                    "title": video.title if video else None,
                    "score": analysis.score,
                    "view_count": video.view_count if video else None,
                    "published_at": video.published_at.isoformat()
                    if video and video.published_at
                    else None,
                }
            )
        if not series:
            logger.warning("channel %s: nothing completed, no score", channel_id)
            return
        slope = trend_slope(series)
        session.add(
            ChannelScore(
                channel_id=channel_id,
                score=view_weighted_score(series),
                trend=Trend(trend_bucket(slope)),
                n_videos=len(series),
                engine_version=ENGINE_VERSION,
                per_video_series_json=series,
            )
        )
        await session.commit()
