from __future__ import annotations

import pytest

from asl_backend.jobs.channel_scoring import trend_bucket, trend_slope, view_weighted_score
from asl_backend.providers.youtube import YouTubeProvider

provider = YouTubeProvider()


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "http://youtube.com/watch?v=dQw4w9WgXcQ&t=42s",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ?si=share_junk",
        "https://m.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://www.youtube.com/shorts/dQw4w9WgXcQ",
        "https://www.youtube.com/embed/dQw4w9WgXcQ",
        "https://www.youtube.com/live/dQw4w9WgXcQ",
        "www.youtube.com/watch?v=dQw4w9WgXcQ",
        "dQw4w9WgXcQ",
    ],
)
def test_normalize_url_variants(url):
    normalized = provider.normalize_url(url)
    assert normalized is not None
    assert normalized.provider_video_id == "dQw4w9WgXcQ"
    assert normalized.canonical_url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


@pytest.mark.parametrize(
    "url",
    [
        "https://vimeo.com/12345",
        "https://example.com/watch?v=dQw4w9WgXcQx",
        "https://www.youtube.com/watch?v=tooshort",
        "not a url at all",
        "",
    ],
)
def test_normalize_url_rejects(url):
    assert provider.normalize_url(url) is None


def test_normalize_channel_url():
    cid = "UC" + "a" * 22
    assert provider.normalize_channel_url(f"https://www.youtube.com/channel/{cid}") == cid
    assert provider.normalize_channel_url(cid) == cid
    assert provider.normalize_channel_url("https://www.youtube.com/@SomeHandle") == "@SomeHandle"
    assert provider.normalize_channel_url("https://example.com/channel/x") is None


def test_view_weighted_score_weights_by_views():
    series = [
        {"score": 90.0, "view_count": 1_000_000},
        {"score": 30.0, "view_count": 1},
    ]
    weighted = view_weighted_score(series)
    assert weighted > 89.9  # the watched video dominates


def test_view_weighted_score_handles_missing_views():
    series = [{"score": 40.0, "view_count": None}, {"score": 60.0, "view_count": 0}]
    assert view_weighted_score(series) == 50.0


def test_trend_buckets():
    speeding = [
        {"score": 40.0 + 2 * i, "published_at": f"2026-01-{i+1:02d}"} for i in range(10)
    ]
    slowing = [
        {"score": 80.0 - 2 * i, "published_at": f"2026-01-{i+1:02d}"} for i in range(10)
    ]
    stable = [{"score": 55.0, "published_at": f"2026-01-{i+1:02d}"} for i in range(10)]
    assert trend_bucket(trend_slope(speeding)) == "speeding_up"
    assert trend_bucket(trend_slope(slowing)) == "slowing_down"
    assert trend_bucket(trend_slope(stable)) == "stable"
    # Publish order matters, not list order.
    assert trend_bucket(trend_slope(list(reversed(speeding)))) == "speeding_up"
