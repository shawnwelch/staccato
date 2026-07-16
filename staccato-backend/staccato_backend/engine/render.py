"""Heat map PNG rendering. Imported lazily — requires matplotlib."""

from __future__ import annotations

import io
from typing import Sequence

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402


def render_heatmap_png(
    bin_centers_s: Sequence[float],
    cuts_per_min: Sequence[float],
    duration_s: float,
    title: str | None = None,
) -> bytes:
    """Render the timeline heat map strip as PNG bytes.

    A single horizontal strip: x = time, brightness = cut density. Neutral
    instrument styling — no red/green judgment colors.
    """
    fig, ax = plt.subplots(figsize=(10, 1.4), dpi=160)
    ax.imshow(
        [list(cuts_per_min)],
        aspect="auto",
        cmap="magma",
        extent=(0.0, float(duration_s), 0.0, 1.0),
        interpolation="nearest",
        vmin=0.0,
    )
    ax.set_yticks([])
    ax.set_xlabel("seconds")
    if title:
        ax.set_title(title, fontsize=9, loc="left")
    fig.tight_layout(pad=0.4)
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return buf.getvalue()
