import type { PacingLabel } from "@/lib/api";
import { formatScore } from "@/lib/format";

// Neutral instrument palette — no red/green judgment.
const LABEL_COLORS: Record<PacingLabel, string> = {
  calm: "#6ea8fe", // cool blue
  moderate: "#2dd4bf", // teal
  fast: "#f5b451", // amber
  "hyper-paced": "#a78bfa", // violet
};

export function labelColor(label: PacingLabel | null): string {
  return label ? LABEL_COLORS[label] : "#8b93a7";
}

export default function ScoreBadge({
  score,
  label,
  size = "md",
}: {
  score: number | null;
  label: PacingLabel | null;
  size?: "sm" | "md" | "lg";
}) {
  const color = labelColor(label);
  const numberSizes = { sm: "1.5rem", md: "3rem", lg: "6.5rem" };
  return (
    <div className={`scoreBadge scoreBadge-${size}`}>
      <span
        className="scoreBadge-number"
        style={{ fontSize: numberSizes[size], color }}
      >
        {formatScore(score)}
      </span>
      {label && (
        <span
          className="chip"
          style={{
            color,
            borderColor: `color-mix(in srgb, ${color} 45%, transparent)`,
            background: `color-mix(in srgb, ${color} 12%, transparent)`,
          }}
        >
          {label}
        </span>
      )}
    </div>
  );
}
