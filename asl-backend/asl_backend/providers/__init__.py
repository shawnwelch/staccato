"""Video provider interface. YouTube first; Vimeo etc. slot in behind this."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class NormalizedVideo:
    provider: str
    provider_video_id: str
    canonical_url: str


@dataclass(frozen=True)
class VideoMetadata:
    title: str | None
    channel_provider_id: str | None
    channel_title: str | None
    duration_s: float | None
    view_count: int | None
    published_at: datetime | None


@dataclass(frozen=True)
class ChannelVideoRef:
    provider_video_id: str
    canonical_url: str
    title: str | None
    view_count: int | None
    published_at: datetime | None


class VideoProvider(Protocol):
    name: str

    def normalize_url(self, url: str) -> NormalizedVideo | None:
        """Parse a user-supplied URL into a canonical video id, or None."""
        ...

    def fetch_metadata(self, video: NormalizedVideo) -> VideoMetadata: ...

    def download_lowres(self, video: NormalizedVideo, dest_dir: Path) -> Path:
        """Fetch the lowest usable resolution — cut detection doesn't need 1080p."""
        ...

    def normalize_channel_url(self, url: str) -> str | None:
        """Parse a channel URL into a provider channel id, or None."""
        ...

    def list_recent_videos(self, provider_channel_id: str, n: int) -> list[ChannelVideoRef]: ...


def get_provider(name: str) -> VideoProvider:
    from asl_backend.providers.youtube import YouTubeProvider

    providers: dict[str, VideoProvider] = {"youtube": YouTubeProvider()}
    try:
        return providers[name]
    except KeyError:
        raise ValueError(f"unknown provider: {name}") from None


def normalize_any_url(url: str) -> NormalizedVideo | None:
    """Try every registered provider."""
    from asl_backend.providers.youtube import YouTubeProvider

    for provider in (YouTubeProvider(),):
        normalized = provider.normalize_url(url)
        if normalized is not None:
            return normalized
    return None
