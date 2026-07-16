"""End-to-end engine verification with synthetic clips, exactly like the
reference module's verification: generate videos with known cut cadences and
assert the detected score. 2s cuts → ≈90, 15s cuts → ≈40."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")

from staccato_backend.engine import analyze  # noqa: E402

FPS = 24
SIZE = (160, 120)  # tiny frames — detection cares about content change, not res


def _write_synthetic_clip(path: Path, shot_length_s: float, duration_s: float) -> None:
    """Alternating high-contrast scenes with per-frame noise, switching every
    shot_length_s. Noise keeps ContentDetector's rolling stats realistic."""
    writer = cv2.VideoWriter(
        str(path), cv2.VideoWriter_fourcc(*"mp4v"), FPS, SIZE
    )
    assert writer.isOpened(), "OpenCV VideoWriter failed to open (mp4v codec missing?)"
    rng = np.random.default_rng(42)
    palette = [
        (30, 30, 30),
        (220, 220, 220),
        (200, 60, 60),
        (60, 200, 200),
        (60, 200, 60),
        (200, 60, 200),
    ]
    total_frames = int(duration_s * FPS)
    frames_per_shot = max(1, int(shot_length_s * FPS))
    for i in range(total_frames):
        scene = (i // frames_per_shot) % len(palette)
        frame = np.full((SIZE[1], SIZE[0], 3), palette[scene], dtype=np.uint8)
        noise = rng.integers(-12, 13, frame.shape, dtype=np.int16)
        frame = np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        writer.write(frame)
    writer.release()


@pytest.mark.slow
def test_fast_clip_scores_hyper_paced(tmp_path):
    clip = tmp_path / "fast.mp4"
    _write_synthetic_clip(clip, shot_length_s=2.0, duration_s=60.0)
    result = analyze(clip)
    assert abs(result["median_shot_s"] - 2.0) < 0.15
    assert 87 <= result["score"] <= 93  # reference: 90.2
    assert result["label"] == "hyper-paced"
    assert result["engine_version"] == "1.0.0"


@pytest.mark.slow
def test_calm_clip_scores_moderate(tmp_path):
    clip = tmp_path / "calm.mp4"
    _write_synthetic_clip(clip, shot_length_s=15.0, duration_s=120.0)
    result = analyze(clip)
    assert abs(result["median_shot_s"] - 15.0) < 0.5
    assert 37 <= result["score"] <= 43  # reference: 40.1
    assert result["label"] == "moderate"


@pytest.mark.slow
def test_heatmap_reflects_burst(tmp_path):
    """First half fast cuts, second half a single static shot."""
    clip = tmp_path / "burst.mp4"
    writer = cv2.VideoWriter(str(clip), cv2.VideoWriter_fourcc(*"mp4v"), FPS, SIZE)
    assert writer.isOpened()
    rng = np.random.default_rng(7)
    palette = [(30, 30, 30), (220, 220, 220), (200, 60, 60), (60, 200, 200)]
    for i in range(30 * FPS):  # 0-30s: cut every 2s
        scene = (i // (2 * FPS)) % len(palette)
        frame = np.full((SIZE[1], SIZE[0], 3), palette[scene], dtype=np.uint8)
        noise = rng.integers(-12, 13, frame.shape, dtype=np.int16)
        writer.write(np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8))
    for i in range(30 * FPS):  # 30-60s: one static shot
        frame = np.full((SIZE[1], SIZE[0], 3), (128, 128, 128), dtype=np.uint8)
        noise = rng.integers(-12, 13, frame.shape, dtype=np.int16)
        writer.write(np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8))
    writer.release()

    result = analyze(clip)
    densities = result["heatmap"]["cuts_per_min"]
    centers = result["heatmap"]["bin_centers_s"]
    first_half = [d for c, d in zip(centers, densities) if c < 25]
    second_half = [d for c, d in zip(centers, densities) if c > 35]
    assert max(first_half) > 20  # ~30 cuts/min in the burst
    assert max(second_half) <= 6  # quiet tail
