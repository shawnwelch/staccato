"""Cut detection via PySceneDetect. Imported lazily — requires OpenCV."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from scenedetect import ContentDetector, detect

from staccato_backend.engine.scoring import CutSummary, summarize_cuts

DEFAULT_THRESHOLD = 27.0


@dataclass(frozen=True)
class DetectionResult:
    cut_times_s: list[float]
    shot_lengths_s: list[float]
    duration_s: float
    threshold: float


def detect_cuts(video_path: str | Path, threshold: float = DEFAULT_THRESHOLD) -> DetectionResult:
    """Run PySceneDetect's ContentDetector over a file.

    Returns interior cut timestamps (shot boundaries, excluding t=0 and
    t=duration) plus the shot lengths they imply.
    """
    scenes = detect(str(video_path), ContentDetector(threshold=threshold))
    if not scenes:
        raise ValueError(f"could not read any frames from {video_path}")
    duration_s = scenes[-1][1].seconds
    cut_times = [start.seconds for start, _ in scenes[1:]]
    lengths = [end.seconds - start.seconds for start, end in scenes]
    return DetectionResult(
        cut_times_s=cut_times,
        shot_lengths_s=lengths,
        duration_s=duration_s,
        threshold=threshold,
    )


def analyze(video_path: str | Path, threshold: float = DEFAULT_THRESHOLD) -> dict:
    """detect_cuts → summarize_cuts, as one dict. The CLI/library entry point."""
    detection = detect_cuts(video_path, threshold=threshold)
    summary: CutSummary = summarize_cuts(detection.cut_times_s, detection.duration_s)
    return {**summary.as_dict(), "cut_times_s": detection.cut_times_s, "threshold": threshold}
