from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return uuid.uuid4().hex


class Base(DeclarativeBase):
    pass


class AnalysisStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    complete = "complete"
    failed = "failed"


class AnalysisSource(str, enum.Enum):
    url = "url"
    upload = "upload"
    optical = "optical"


class EntitlementPlan(str, enum.Enum):
    free = "free"
    pro = "pro"


class EntitlementSource(str, enum.Enum):
    apple = "apple"
    stripe = "stripe"
    promo = "promo"


class EntitlementStatus(str, enum.Enum):
    active = "active"
    grace = "grace"
    expired = "expired"
    revoked = "revoked"


class Trend(str, enum.Enum):
    speeding_up = "speeding_up"
    stable = "stable"
    slowing_down = "slowing_down"


class User(Base):
    __tablename__ = "users"

    # Mirror of the Clerk user id — Clerk is the source of truth for identity.
    clerk_user_id: Mapped[str] = mapped_column(String(191), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Entitlement(Base):
    __tablename__ = "entitlements"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.clerk_user_id"), index=True)
    plan: Mapped[EntitlementPlan] = mapped_column(Enum(EntitlementPlan))
    # Where the subscription came from is a column, not a schema fork —
    # Stripe web checkout can land later without a migration.
    source: Mapped[EntitlementSource] = mapped_column(Enum(EntitlementSource))
    status: Mapped[EntitlementStatus] = mapped_column(Enum(EntitlementStatus))
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    original_transaction_id: Mapped[str | None] = mapped_column(String(191), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class UsageCounter(Base):
    __tablename__ = "usage_counters"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.clerk_user_id"), primary_key=True)
    # Incremented under SELECT ... FOR UPDATE so concurrent submits can't
    # both take the last free slot.
    free_analyses_used: Mapped[int] = mapped_column(Integer, default=0)


class Channel(Base):
    __tablename__ = "channels"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    provider: Mapped[str] = mapped_column(String(32), default="youtube")
    provider_channel_id: Mapped[str] = mapped_column(String(191))
    title: Mapped[str | None] = mapped_column(String(512))
    subscriber_count: Mapped[int | None] = mapped_column(Integer)
    category: Mapped[str | None] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (UniqueConstraint("provider", "provider_channel_id"),)


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    provider: Mapped[str] = mapped_column(String(32))
    provider_video_id: Mapped[str] = mapped_column(String(191))
    title: Mapped[str | None] = mapped_column(String(512))
    channel_id: Mapped[str | None] = mapped_column(ForeignKey("channels.id"), index=True)
    channel_title: Mapped[str | None] = mapped_column(String(512))
    duration_s: Mapped[float | None] = mapped_column(Float)
    view_count: Mapped[int | None] = mapped_column(Integer)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    channel: Mapped[Channel | None] = relationship()

    __table_args__ = (UniqueConstraint("provider", "provider_video_id"),)


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    video_id: Mapped[str | None] = mapped_column(ForeignKey("videos.id"), index=True)
    requested_by: Mapped[str | None] = mapped_column(ForeignKey("users.clerk_user_id"), index=True)
    status: Mapped[AnalysisStatus] = mapped_column(Enum(AnalysisStatus), index=True)
    source: Mapped[AnalysisSource] = mapped_column(Enum(AnalysisSource))
    engine_version: Mapped[str] = mapped_column(String(32))
    input_url: Mapped[str | None] = mapped_column(Text)

    score: Mapped[float | None] = mapped_column(Float)
    label: Mapped[str | None] = mapped_column(String(32))
    median_shot_s: Mapped[float | None] = mapped_column(Float)
    cuts_per_minute: Mapped[float | None] = mapped_column(Float)
    cut_count: Mapped[int | None] = mapped_column(Integer)
    duration_s: Mapped[float | None] = mapped_column(Float)
    result_json_url: Mapped[str | None] = mapped_column(Text)
    heatmap_png_url: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    video: Mapped[Video | None] = relationship()


class ChannelScore(Base):
    __tablename__ = "channel_scores"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    channel_id: Mapped[str] = mapped_column(ForeignKey("channels.id"), index=True)
    score: Mapped[float] = mapped_column(Float)
    trend: Mapped[Trend] = mapped_column(Enum(Trend))
    n_videos: Mapped[int] = mapped_column(Integer)
    engine_version: Mapped[str] = mapped_column(String(32))
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # Per-video series: [{provider_video_id, title, score, view_count, published_at}]
    per_video_series_json: Mapped[list] = mapped_column(JSON, default=list)

    channel: Mapped[Channel] = relationship()


class LiveSession(Base):
    __tablename__ = "live_sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.clerk_user_id"), index=True)
    content_label: Mapped[str] = mapped_column(String(512), default="unknown")
    device_summary_json: Mapped[dict] = mapped_column(JSON)
    duration_s: Mapped[float] = mapped_column(Float)
    cut_count: Mapped[int] = mapped_column(Integer)
    device_score: Mapped[float | None] = mapped_column(Float)
    # Recomputed server-side from submitted cut times — client math is never
    # trusted for published data.
    recomputed_score: Mapped[float] = mapped_column(Float)
    label: Mapped[str] = mapped_column(String(32))
    engine_version: Mapped[str] = mapped_column(String(32))
    # Optical scans stay out of canonical title scores until moderated.
    promoted: Mapped[bool] = mapped_column(Boolean, default=False)
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SharePage(Base):
    __tablename__ = "share_pages"

    slug: Mapped[str] = mapped_column(String(24), primary_key=True)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id"), index=True, unique=True)
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    analysis: Mapped[Analysis] = relationship()
