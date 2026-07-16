"""Pure scoring math: pacing score + heat map.

Nothing here touches video files or the network — inputs are cut timestamps
and durations, outputs are numbers. The Swift port in asl-apple must match
this bit-for-bit at the same ENGINE_VERSION; both are pinned by the shared
golden vectors in fixtures/golden_vectors.json.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Sequence

# Any change to these constants (or to the median basis) is a new engine
# version: every stored score carries ENGINE_VERSION and is never silently
# rescored.
ENGINE_VERSION = "1.0.0"

_PIVOT_SECONDS = 11.0  # median shot length that maps to score 50
_STEEPNESS = 1.3  # logistic exponent

LABELS = ("calm", "moderate", "fast", "hyper-paced")

_DEFAULT_BIN_S = 2.0
_DEFAULT_WINDOW_S = 10.0


def pacing_score(median_shot_length_s: float) -> float:
    """0–100 pacing intensity from the MEDIAN shot length.

    Logistic in log-space of shot length: score = 100 / (1 + (m / 11) ^ 1.3).
    Anchors: 34s → ~19 (calm), 11s → 50, 3s → ~84, 1.5s → ~93 (hyper-paced).
    Median (not mean) so long intros/credits don't skew the result.
    """
    if median_shot_length_s <= 0:
        raise ValueError("median shot length must be positive")
    return 100.0 / (1.0 + (median_shot_length_s / _PIVOT_SECONDS) ** _STEEPNESS)


def label_for_score(score: float) -> str:
    """Neutral pacing label. <25 calm, <50 moderate, <75 fast, else hyper-paced."""
    if score < 25.0:
        return LABELS[0]
    if score < 50.0:
        return LABELS[1]
    if score < 75.0:
        return LABELS[2]
    return LABELS[3]


def shot_lengths(cut_times: Sequence[float], duration_s: float) -> list[float]:
    """Shot lengths implied by cut timestamps within [0, duration].

    Cuts are boundaries; a video with k cuts has k+1 shots (first shot starts
    at 0, last shot ends at duration). Zero-length shots (duplicate cut
    timestamps) are dropped.
    """
    if duration_s <= 0:
        raise ValueError("duration must be positive")
    boundaries = [0.0, *sorted(float(t) for t in cut_times if 0.0 < t < duration_s), duration_s]
    return [b - a for a, b in zip(boundaries, boundaries[1:]) if b - a > 0.0]


def build_heatmap(
    cut_times: Sequence[float],
    duration_s: float,
    bin_s: float = _DEFAULT_BIN_S,
    window_s: float = _DEFAULT_WINDOW_S,
) -> tuple[list[float], list[float]]:
    """Rolling cut density over the timeline, normalized to cuts/min.

    The timeline is split into bins of `bin_s`. For each bin center t, count
    the cuts inside the centered window [t - window_s/2, t + window_s/2)
    clipped to [0, duration], and normalize by the CLIPPED window length so
    edge bins aren't artificially deflated.

    Returns (bin_centers_s, cuts_per_min), both len == ceil(duration / bin_s).
    """
    if duration_s <= 0:
        raise ValueError("duration must be positive")
    if bin_s <= 0 or window_s <= 0:
        raise ValueError("bin_s and window_s must be positive")

    cuts = sorted(float(t) for t in cut_times if 0.0 <= t <= duration_s)
    n_bins = max(1, math.ceil(duration_s / bin_s))
    half = window_s / 2.0

    centers: list[float] = []
    densities: list[float] = []
    for i in range(n_bins):
        center = (i + 0.5) * bin_s
        lo = max(0.0, center - half)
        hi = min(duration_s, center + half)
        count = sum(1 for t in cuts if lo <= t < hi)
        span = hi - lo
        centers.append(center)
        densities.append((count / span) * 60.0 if span > 0 else 0.0)
    return centers, densities


@dataclass(frozen=True)
class CutSummary:
    """Everything a surface needs to display a result."""

    engine_version: str
    duration_s: float
    cut_count: int
    median_shot_s: float
    cuts_per_minute: float
    score: float
    label: str
    heatmap_bin_centers_s: list[float]
    heatmap_cuts_per_min: list[float]

    def as_dict(self) -> dict:
        return {
            "engine_version": self.engine_version,
            "duration_s": self.duration_s,
            "cut_count": self.cut_count,
            "median_shot_s": self.median_shot_s,
            "cuts_per_minute": self.cuts_per_minute,
            "score": self.score,
            "label": self.label,
            "heatmap": {
                "bin_centers_s": self.heatmap_bin_centers_s,
                "cuts_per_min": self.heatmap_cuts_per_min,
            },
        }


def summarize_cuts(
    cut_times: Sequence[float],
    duration_s: float,
    bin_s: float = _DEFAULT_BIN_S,
    window_s: float = _DEFAULT_WINDOW_S,
) -> CutSummary:
    """Full scoring pipeline from cut timestamps (the shared entry point).

    Used by the URL worker (with detected cuts) and by live-session
    recomputation (with device-submitted cuts) so client math is never
    trusted for published data.
    """
    lengths = shot_lengths(cut_times, duration_s)
    median = statistics.median(lengths)
    score = pacing_score(median)
    centers, densities = build_heatmap(cut_times, duration_s, bin_s=bin_s, window_s=window_s)
    in_range = sum(1 for t in cut_times if 0.0 < float(t) < duration_s)
    return CutSummary(
        engine_version=ENGINE_VERSION,
        duration_s=float(duration_s),
        cut_count=in_range,
        median_shot_s=float(median),
        cuts_per_minute=in_range / (duration_s / 60.0),
        score=score,
        label=label_for_score(score),
        heatmap_bin_centers_s=centers,
        heatmap_cuts_per_min=densities,
    )
