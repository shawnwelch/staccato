"""CLI: python -m asl_backend.engine clip.mp4 --heatmap out.png --json out.json"""

from __future__ import annotations

import argparse
import json
import sys

from asl_backend.engine import analyze
from asl_backend.engine.detect import DEFAULT_THRESHOLD


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pacing-scorer", description="Score video pacing.")
    parser.add_argument("video", help="path to a video file")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--heatmap", metavar="PNG", help="write heat map PNG here")
    parser.add_argument("--json", metavar="JSON", help="write full result JSON here")
    args = parser.parse_args(argv)

    result = analyze(args.video, threshold=args.threshold)
    print(
        f"score {result['score']:.1f} ({result['label']}) — "
        f"median shot {result['median_shot_s']:.2f}s, "
        f"{result['cuts_per_minute']:.1f} cuts/min over {result['duration_s']:.1f}s"
    )
    if args.heatmap:
        from asl_backend.engine.render import render_heatmap_png

        png = render_heatmap_png(
            result["heatmap"]["bin_centers_s"],
            result["heatmap"]["cuts_per_min"],
            result["duration_s"],
        )
        with open(args.heatmap, "wb") as f:
            f.write(png)
    if args.json:
        with open(args.json, "w") as f:
            json.dump(result, f, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
