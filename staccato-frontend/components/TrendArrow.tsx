import type { Trend } from "@/lib/api";

const TRENDS: Record<Trend, { arrow: string; text: string }> = {
  speeding_up: { arrow: "↗", text: "speeding up" },
  stable: { arrow: "→", text: "stable" },
  slowing_down: { arrow: "↘", text: "slowing down" },
};

export default function TrendArrow({
  trend,
  withText = false,
}: {
  trend: Trend;
  withText?: boolean;
}) {
  const t = TRENDS[trend] ?? TRENDS.stable;
  return (
    <span className="trend" title={t.text} aria-label={t.text}>
      <span className="trend-arrow" aria-hidden="true">
        {t.arrow}
      </span>
      {withText && <span className="trend-text">{t.text}</span>}
    </span>
  );
}
