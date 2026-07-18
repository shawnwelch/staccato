import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getShare, NOT_FOUND } from "@/lib/api";
import ScoreBadge from "@/components/ScoreBadge";
import HeatmapStrip from "@/components/HeatmapStrip";
import {
  formatCount,
  formatDuration,
  formatScore,
  formatSeconds,
} from "@/lib/format";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const data = await getShare(slug);
  if (data === NOT_FOUND || data === null) {
    return { title: "Staccato Score" };
  }
  const title = data.video?.title ?? "Video";
  const score =
    data.analysis.score != null ? formatScore(data.analysis.score) : "pending";
  const pageTitle = `${title} — Staccato Score ${score}`;
  const description =
    data.analysis.label != null
      ? `${data.analysis.label} pacing — median shot ${formatSeconds(
          data.analysis.median_shot_s,
        )}, ${data.analysis.cuts_per_minute?.toFixed(1) ?? "—"} cuts/min. Measured by Staccato.`
      : "Shot-pacing measurement by Staccato.";
  return {
    title: pageTitle,
    description,
    openGraph: {
      title: pageTitle,
      description,
      type: "website",
      siteName: "Staccato",
    },
    twitter: {
      card: "summary_large_image",
      title: pageTitle,
      description,
    },
  };
}

export default async function SharePage({ params }: Props) {
  const { slug } = await params;
  const data = await getShare(slug);

  if (data === NOT_FOUND) notFound();

  if (data === null) {
    return (
      <>
        <h1>Staccato Score</h1>
        <div className="notice">
          This score is temporarily unavailable &mdash; we couldn&apos;t reach
          the scoring service. Try again in a moment.
        </div>
        <Link href="/">Back to Staccato</Link>
      </>
    );
  }

  const { analysis, video } = data;
  const title = video?.title ?? "Untitled video";

  if (analysis.status !== "complete") {
    const failed = analysis.status === "failed";
    return (
      <>
        <p className="small faint mono" style={{ margin: 0 }}>
          {video?.provider ?? "video"}
        </p>
        <h1>{title}</h1>
        {video?.channel_title && <p className="dim">{video.channel_title}</p>}
        <div className="notice">
          {failed ? (
            <>
              This analysis didn&apos;t finish &mdash; the video couldn&apos;t
              be measured. Try scanning it again from the app.
            </>
          ) : (
            <>
              Measuring&hellip; this analysis is{" "}
              <span className="mono">{analysis.status}</span>. Check back
              shortly &mdash; scoring usually takes under a minute.
            </>
          )}
        </div>
        <p className="small faint">engine v{analysis.engine_version}</p>
      </>
    );
  }

  return (
    <>
      <p className="small faint mono" style={{ margin: 0 }}>
        {video?.provider ?? "video"} &middot; {data.view_count.toLocaleString()}{" "}
        score views
      </p>
      <h1 style={{ marginBottom: "0.15rem" }}>{title}</h1>
      {video?.channel_title && (
        <p className="dim" style={{ marginTop: 0 }}>
          {video.channel_title}
          {video.view_count != null && (
            <span className="faint">
              {" "}
              &middot; {formatCount(video.view_count)} views
            </span>
          )}
        </p>
      )}

      <div className="card" style={{ marginTop: "1.5rem" }}>
        <div className="scorePanel">
          <ScoreBadge score={analysis.score} label={analysis.label} size="lg" />
          <div className="dim" style={{ maxWidth: "18rem" }}>
            The Staccato Score: pacing intensity, 0&ndash;100. Derived from how
            often this video changes shots.
          </div>
        </div>
      </div>

      <h2>Cut density over time</h2>
      <HeatmapStrip src={analysis.heatmap_png_url} />

      <dl className="statGrid">
        <div className="stat">
          <dt>Median shot</dt>
          <dd>{formatSeconds(analysis.median_shot_s)}</dd>
        </div>
        <div className="stat">
          <dt>Cuts / min</dt>
          <dd>
            {analysis.cuts_per_minute != null
              ? analysis.cuts_per_minute.toFixed(1)
              : "—"}
          </dd>
        </div>
        <div className="stat">
          <dt>Total cuts</dt>
          <dd>
            {analysis.cut_count != null
              ? analysis.cut_count.toLocaleString()
              : "—"}
          </dd>
        </div>
        <div className="stat">
          <dt>Duration</dt>
          <dd>{formatDuration(analysis.duration_s)}</dd>
        </div>
      </dl>

      <div className="ctaBlock">
        <div>
          <strong>Scan your own</strong>
          <div className="small dim">
            Measure any video&apos;s pacing with the Staccato iOS app.
          </div>
        </div>
        <a className="btn btn-primary" href="https://apps.apple.com" rel="noopener">
          Get the iOS app
        </a>
      </div>

      <p className="small faint">
        engine v{analysis.engine_version} &middot; scores are versioned and
        never silently rescored &middot;{" "}
        <Link href="/methodology">methodology</Link>
      </p>
    </>
  );
}
