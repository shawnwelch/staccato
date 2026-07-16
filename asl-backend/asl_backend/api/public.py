"""Unauthenticated read endpoints — the SEO/growth surface. Cached hard."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from asl_backend.api.serializers import analysis_out, video_out
from asl_backend.db import get_session
from asl_backend.models import (
    Analysis,
    AnalysisStatus,
    Channel,
    ChannelScore,
    SharePage,
    Video,
)
from asl_backend.schemas import (
    ChannelOut,
    ChannelScoreOut,
    LeaderboardItem,
    LeaderboardResponse,
    SeriesPointOut,
    SharePageResponse,
    VideoLookupResponse,
)

router = APIRouter(prefix="/v1", tags=["public"])

_CACHE_HEADER = "public, max-age=60, s-maxage=300, stale-while-revalidate=600"


@router.get("/share/{slug}", response_model=SharePageResponse)
async def get_share_page(
    slug: str,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> SharePageResponse:
    share = await session.get(SharePage, slug)
    if share is None:
        raise HTTPException(status_code=404, detail="share page not found")
    analysis = await session.get(Analysis, share.analysis_id)
    video = await session.get(Video, analysis.video_id) if analysis.video_id else None
    # Fire-and-forget view counting; contention doesn't matter for a counter.
    await session.execute(
        update(SharePage).where(SharePage.slug == slug).values(view_count=SharePage.view_count + 1)
    )
    await session.commit()
    response.headers["Cache-Control"] = _CACHE_HEADER
    return SharePageResponse(
        slug=share.slug,
        view_count=share.view_count + 1,
        analysis=analysis_out(analysis),
        video=video_out(video),
    )


@router.get("/videos/{provider}/{provider_video_id}", response_model=VideoLookupResponse)
async def get_video(
    provider: str,
    provider_video_id: str,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> VideoLookupResponse:
    video = await session.scalar(
        select(Video).where(
            Video.provider == provider, Video.provider_video_id == provider_video_id
        )
    )
    if video is None:
        raise HTTPException(status_code=404, detail="video not scored yet")
    analysis = await session.scalar(
        select(Analysis)
        .where(Analysis.video_id == video.id, Analysis.status == AnalysisStatus.complete)
        .order_by(Analysis.completed_at.desc())
    )
    share = None
    if analysis is not None:
        share = await session.scalar(
            select(SharePage).where(SharePage.analysis_id == analysis.id)
        )
    response.headers["Cache-Control"] = _CACHE_HEADER
    return VideoLookupResponse(
        video=video_out(video),
        analysis=analysis_out(analysis) if analysis else None,
        share_slug=share.slug if share else None,
    )


def _score_out(score_row: ChannelScore) -> ChannelScoreOut:
    return ChannelScoreOut(
        score=score_row.score,
        trend=score_row.trend.value,
        n_videos=score_row.n_videos,
        engine_version=score_row.engine_version,
        computed_at=score_row.computed_at,
        series=[SeriesPointOut(**p) for p in (score_row.per_video_series_json or [])],
    )


@router.get("/channels/{channel_id}", response_model=ChannelOut)
async def get_channel(
    channel_id: str,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> ChannelOut:
    channel = await session.get(Channel, channel_id)
    if channel is None:
        channel = await session.scalar(
            select(Channel).where(Channel.provider_channel_id == channel_id)
        )
    if channel is None:
        raise HTTPException(status_code=404, detail="channel not found")
    latest = await session.scalar(
        select(ChannelScore)
        .where(ChannelScore.channel_id == channel.id)
        .order_by(ChannelScore.computed_at.desc())
    )
    response.headers["Cache-Control"] = _CACHE_HEADER
    return ChannelOut(
        id=channel.id,
        provider_channel_id=channel.provider_channel_id,
        title=channel.title,
        subscriber_count=channel.subscriber_count,
        category=channel.category,
        score=_score_out(latest) if latest else None,
    )


@router.get("/leaderboard", response_model=LeaderboardResponse)
async def get_leaderboard(
    response: Response,
    category: str | None = None,
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> LeaderboardResponse:
    # Latest score per channel.
    latest_at = (
        select(
            ChannelScore.channel_id,
            func.max(ChannelScore.computed_at).label("latest_at"),
        )
        .group_by(ChannelScore.channel_id)
        .subquery()
    )
    base = (
        select(ChannelScore, Channel)
        .join(
            latest_at,
            (ChannelScore.channel_id == latest_at.c.channel_id)
            & (ChannelScore.computed_at == latest_at.c.latest_at),
        )
        .join(Channel, Channel.id == ChannelScore.channel_id)
    )
    if category:
        base = base.where(Channel.category == category)

    rows = (await session.execute(base)).all()
    rows.sort(key=lambda r: r[0].score, reverse=(order == "desc"))
    total = len(rows)
    start = (page - 1) * page_size
    page_rows = rows[start : start + page_size]

    categories = [
        c
        for c in (
            await session.scalars(
                select(Channel.category).where(Channel.category.is_not(None)).distinct()
            )
        ).all()
    ]

    response.headers["Cache-Control"] = _CACHE_HEADER
    return LeaderboardResponse(
        items=[
            LeaderboardItem(
                rank=start + i + 1,
                channel_id=channel.id,
                title=channel.title,
                category=channel.category,
                subscriber_count=channel.subscriber_count,
                score=score.score,
                trend=score.trend.value,
                n_videos=score.n_videos,
                computed_at=score.computed_at,
            )
            for i, (score, channel) in enumerate(page_rows)
        ],
        page=page,
        page_size=page_size,
        total=total,
        categories=sorted(categories),
    )
