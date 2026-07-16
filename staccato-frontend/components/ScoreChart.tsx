import type { SeriesPoint } from "@/lib/api";
import { labelForScore } from "@/lib/api";
import { labelColor } from "@/components/ScoreBadge";
import { formatDate } from "@/lib/format";

// Hand-rolled server-rendered SVG line/dot chart of per-video pacing scores
// over publish date. No chart library.
export default function ScoreChart({ series }: { series: SeriesPoint[] }) {
  const points = series
    .filter((p) => p.score != null && Number.isFinite(p.score))
    .slice()
    .sort((a, b) => {
      const ta = a.published_at ? Date.parse(a.published_at) : 0;
      const tb = b.published_at ? Date.parse(b.published_at) : 0;
      return ta - tb;
    });

  if (points.length === 0) {
    return <div className="chart-empty">No scored videos yet.</div>;
  }

  const W = 720;
  const H = 240;
  const PAD = { top: 16, right: 16, bottom: 28, left: 36 };
  const iw = W - PAD.left - PAD.right;
  const ih = H - PAD.top - PAD.bottom;

  const times = points.map((p, i) =>
    p.published_at ? Date.parse(p.published_at) : i,
  );
  const tMin = Math.min(...times);
  const tMax = Math.max(...times);
  const span = tMax - tMin || 1;

  const x = (i: number) =>
    points.length === 1
      ? PAD.left + iw / 2
      : PAD.left + ((times[i] - tMin) / span) * iw;
  const y = (score: number) =>
    PAD.top + ih - (Math.max(0, Math.min(100, score)) / 100) * ih;

  const path = points
    .map((p, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(p.score).toFixed(1)}`)
    .join(" ");

  const gridLines = [0, 25, 50, 75, 100];
  const first = points[0];
  const last = points[points.length - 1];

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="chart"
      role="img"
      aria-label="Per-video pacing score over publish date"
    >
      {gridLines.map((g) => (
        <g key={g}>
          <line
            x1={PAD.left}
            x2={W - PAD.right}
            y1={y(g)}
            y2={y(g)}
            stroke="var(--grid)"
            strokeWidth="1"
            strokeDasharray={g === 0 || g === 100 ? undefined : "3 5"}
          />
          <text
            x={PAD.left - 8}
            y={y(g) + 3.5}
            textAnchor="end"
            className="chart-tick"
          >
            {g}
          </text>
        </g>
      ))}
      <path d={path} fill="none" stroke="var(--line)" strokeWidth="1.5" />
      {points.map((p, i) => (
        <circle
          key={`${p.provider_video_id}-${i}`}
          cx={x(i)}
          cy={y(p.score)}
          r="3.5"
          fill={labelColor(labelForScore(p.score))}
          stroke="var(--bg)"
          strokeWidth="1"
        >
          <title>
            {`${p.title ?? p.provider_video_id} — ${Math.round(p.score)} (${formatDate(p.published_at)})`}
          </title>
        </circle>
      ))}
      <text x={PAD.left} y={H - 8} className="chart-tick">
        {formatDate(first.published_at)}
      </text>
      <text x={W - PAD.right} y={H - 8} textAnchor="end" className="chart-tick">
        {formatDate(last.published_at)}
      </text>
    </svg>
  );
}
