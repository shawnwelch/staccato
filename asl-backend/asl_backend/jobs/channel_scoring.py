"""Pure channel-scoring math (unit-tested without a DB).

Channel score = view-weighted average of the last N videos' scores, so the
number reflects what actually gets watched. Trend = least-squares slope of
score over the videos ordered by publish date, bucketed.
"""

from __future__ import annotations

from typing import Iterable, TypedDict

# Slope is in score-points per video (publish order). Within ±this, "stable".
TREND_SLOPE_THRESHOLD = 0.5


class SeriesPoint(TypedDict, total=False):
    provider_video_id: str
    title: str | None
    score: float
    view_count: int | None
    published_at: str | None  # ISO 8601


def view_weighted_score(series: Iterable[SeriesPoint]) -> float:
    points = list(series)
    if not points:
        raise ValueError("empty series")
    # Missing/zero view counts get weight 1 so brand-new videos still count.
    weights = [max(1.0, float(p.get("view_count") or 0)) for p in points]
    total = sum(weights)
    return sum(p["score"] * w for p, w in zip(points, weights)) / total


def trend_slope(series: list[SeriesPoint]) -> float:
    """Least-squares slope of score vs publish-order index (oldest first)."""
    ordered = sorted(series, key=lambda p: (p.get("published_at") is None, p.get("published_at")))
    ys = [p["score"] for p in ordered]
    n = len(ys)
    if n < 2:
        return 0.0
    xs = list(range(n))
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    denom = sum((x - mean_x) ** 2 for x in xs)
    if denom == 0:
        return 0.0
    return sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / denom


def trend_bucket(slope: float) -> str:
    if slope > TREND_SLOPE_THRESHOLD:
        return "speeding_up"
    if slope < -TREND_SLOPE_THRESHOLD:
        return "slowing_down"
    return "stable"
