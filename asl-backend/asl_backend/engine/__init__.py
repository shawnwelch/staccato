"""Pacing scoring engine — the open-core module.

This package is deliberately dependency-light (numpy only for the hot path,
PySceneDetect/OpenCV only when `detect_cuts` is actually called, matplotlib
only when a heat-map PNG is rendered) and imports NOTHING from the rest of
asl_backend, so it can be extracted into a standalone OSS repo verbatim.

The score formula is product surface area: any change to the constants in
`scoring.py` or to the median basis changes every published score. Bump
ENGINE_VERSION for any such change and never silently rescore.
"""

from asl_backend.engine.scoring import (
    ENGINE_VERSION,
    LABELS,
    build_heatmap,
    label_for_score,
    pacing_score,
    summarize_cuts,
)

__all__ = [
    "ENGINE_VERSION",
    "LABELS",
    "build_heatmap",
    "label_for_score",
    "pacing_score",
    "summarize_cuts",
    "detect_cuts",
    "analyze",
]


def detect_cuts(video_path, threshold: float = 27.0):
    """Lazy re-export so importing the engine never requires OpenCV."""
    from asl_backend.engine.detect import detect_cuts as _detect_cuts

    return _detect_cuts(video_path, threshold=threshold)


def analyze(video_path, threshold: float = 27.0):
    """Lazy re-export of the full-pipeline convenience entry point."""
    from asl_backend.engine.detect import analyze as _analyze

    return _analyze(video_path, threshold=threshold)
