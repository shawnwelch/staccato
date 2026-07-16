import Link from "next/link";
import ScoreBadge from "@/components/ScoreBadge";

export const dynamic = "force-dynamic";

// Deterministic mock heat-map bars for the sample card (no data fetch).
const SAMPLE_BARS = [
  22, 35, 60, 88, 74, 92, 66, 40, 55, 78, 95, 83, 61, 47, 70, 90, 82, 58, 36,
  50, 72, 86, 64, 44, 30, 52, 76, 91, 68, 42,
];

function barColor(v: number): string {
  if (v < 40) return "#2a3350";
  if (v < 65) return "#3d5a8f";
  if (v < 85) return "#6ea8fe";
  return "#a78bfa";
}

export default function HomePage() {
  return (
    <>
      <h1>See how fast anything cuts.</h1>
      <p className="lede">
        Staccato measures a video&apos;s shot pacing: a 0&ndash;100 intensity score
        from median shot length, plus a timeline heat map of cut density. A
        neutral instrument &mdash; point it at any video and read the number.
      </p>

      <div className="card sampleCard" aria-label="Sample score card">
        <div className="sampleMeta">
          <div className="small faint mono">SAMPLE &middot; youtube</div>
          <div style={{ fontWeight: 600 }}>
            Epic 60-Second Gadget Montage
          </div>
          <div className="small dim">Sample Channel</div>
        </div>
        <div className="scorePanel">
          <ScoreBadge score={81} label="hyper-paced" size="md" />
          <div className="small dim">
            <div>
              median shot <span className="mono">1.4s</span>
            </div>
            <div>
              cuts/min <span className="mono">41.2</span>
            </div>
          </div>
        </div>
        <div className="sampleBars" role="img" aria-label="Sample cut-density heat map">
          {SAMPLE_BARS.map((v, i) => (
            <span
              key={i}
              style={{ height: `${v}%`, background: barColor(v) }}
            />
          ))}
        </div>
        <p className="small faint" style={{ marginBottom: 0 }}>
          engine v1.0.0 &middot; sample data
        </p>
      </div>

      <div className="ctaRow">
        <a className="btn btn-primary" href="https://apps.apple.com" rel="noopener">
          Scan your own &mdash; get the iOS app
        </a>
        <Link className="btn" href="/leaderboard">
          Browse the channel leaderboard
        </Link>
      </div>

      <h2>What the number means</h2>
      <p className="dim" style={{ maxWidth: "42rem" }}>
        The score maps median shot length onto a 0&ndash;100 scale &mdash; a
        median of 11 seconds sits at 50. Labels are descriptive bands: calm,
        moderate, fast, hyper-paced. Details in the{" "}
        <Link href="/methodology">methodology</Link>.
      </p>
    </>
  );
}
