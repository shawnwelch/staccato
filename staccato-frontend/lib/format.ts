export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null || !Number.isFinite(seconds)) return "—";
  const total = Math.round(seconds);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${m}:${String(s).padStart(2, "0")}`;
}

export function formatCount(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return "—";
  if (n >= 1_000_000_000) return `${trim(n / 1_000_000_000)}B`;
  if (n >= 1_000_000) return `${trim(n / 1_000_000)}M`;
  if (n >= 1_000) return `${trim(n / 1_000)}K`;
  return String(n);
}

function trim(x: number): string {
  return x >= 10 ? String(Math.round(x)) : x.toFixed(1).replace(/\.0$/, "");
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

export function formatSeconds(s: number | null | undefined): string {
  if (s == null || !Number.isFinite(s)) return "—";
  return `${s.toFixed(1)}s`;
}

export function formatScore(score: number | null | undefined): string {
  if (score == null || !Number.isFinite(score)) return "—";
  return String(Math.round(score));
}
