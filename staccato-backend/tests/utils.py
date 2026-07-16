from __future__ import annotations

from pathlib import Path


def write_synthetic_clip(path: Path, shot_length_s: float, duration_s: float, fps: int = 24) -> None:
    import cv2
    import numpy as np

    size = (160, 120)
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, size)
    assert writer.isOpened()
    rng = np.random.default_rng(42)
    palette = [
        (30, 30, 30),
        (220, 220, 220),
        (200, 60, 60),
        (60, 200, 200),
        (60, 200, 60),
        (200, 60, 200),
    ]
    frames_per_shot = max(1, int(shot_length_s * fps))
    for i in range(int(duration_s * fps)):
        scene = (i // frames_per_shot) % len(palette)
        frame = np.full((size[1], size[0], 3), palette[scene], dtype=np.uint8)
        noise = rng.integers(-12, 13, frame.shape, dtype=np.int16)
        frame = np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        writer.write(frame)
    writer.release()
