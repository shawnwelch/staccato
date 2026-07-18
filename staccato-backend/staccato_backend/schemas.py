from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field


class AnalysisCreateRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2048)


class VideoOut(BaseModel):
    provider: str
    provider_video_id: str
    title: str | None = None
    channel_title: str | None = None
    duration_s: float | None = None
    view_count: int | None = None
    published_at: datetime | None = None


class AnalysisOut(BaseModel):
    id: str
    status: Literal["queued", "running", "complete", "failed"]
    engine_version: str
    score: float | None = None
    label: str | None = None
    median_shot_s: float | None = None
    cuts_per_minute: float | None = None
    cut_count: int | None = None
    duration_s: float | None = None
    heatmap_png_url: str | None = None
    result_json_url: str | None = None
    source: Literal["url", "upload", "optical"]
    error: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class EntitlementOut(BaseModel):
    plan: Literal["free", "pro"]
    source: str | None = None
    status: str
    free_analyses_used: int
    free_analyses_limit: int
    free_remaining: int


class AnalysisCreateResponse(BaseModel):
    analysis: AnalysisOut
    video: VideoOut | None = None
    share_slug: str | None = None
    deduped: bool = False
    entitlement: EntitlementOut


class AnalysisStatusResponse(BaseModel):
    analysis: AnalysisOut
    video: VideoOut | None = None
    share_slug: str | None = None


class LiveSessionCreateRequest(BaseModel):
    # Bounded + finite: heat-map size scales with duration, so an unbounded
    # duration (or NaN/inf smuggled through JSON floats) is a memory/CPU DoS
    # vector. The per-deploy duration ceiling is enforced in the endpoint
    # (settings.live_session_max_duration_s).
    cut_times_s: list[Annotated[float, Field(allow_inf_nan=False)]] = Field(max_length=100_000)
    duration_s: float = Field(gt=0, allow_inf_nan=False)
    device_score: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)
    content_label: str = Field(default="unknown", max_length=512)


class LiveSessionOut(BaseModel):
    id: str
    recomputed_score: float
    label: str
    cut_count: int
    median_shot_s: float
    cuts_per_minute: float
    engine_version: str
    device_score: float | None
    promoted: bool


class SeriesPointOut(BaseModel):
    provider_video_id: str
    title: str | None = None
    score: float
    view_count: int | None = None
    published_at: datetime | None = None


class ChannelScoreOut(BaseModel):
    score: float
    trend: Literal["speeding_up", "stable", "slowing_down"]
    n_videos: int
    engine_version: str
    computed_at: datetime
    series: list[SeriesPointOut]


class ChannelOut(BaseModel):
    id: str
    provider_channel_id: str
    title: str | None
    subscriber_count: int | None = None
    category: str | None = None
    score: ChannelScoreOut | None = None


class LeaderboardItem(BaseModel):
    rank: int
    channel_id: str
    title: str | None
    category: str | None = None
    subscriber_count: int | None = None
    score: float
    trend: str
    n_videos: int
    computed_at: datetime


class LeaderboardResponse(BaseModel):
    items: list[LeaderboardItem]
    page: int
    page_size: int
    total: int
    categories: list[str]


class SharePageResponse(BaseModel):
    slug: str
    view_count: int
    analysis: AnalysisOut
    video: VideoOut | None = None


class VideoLookupResponse(BaseModel):
    video: VideoOut
    analysis: AnalysisOut | None = None
    share_slug: str | None = None
