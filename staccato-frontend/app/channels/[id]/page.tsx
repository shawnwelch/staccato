import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getChannel, labelForScore, NOT_FOUND } from "@/lib/api";
import ScoreBadge, { labelColor } from "@/components/ScoreBadge";
import TrendArrow from "@/components/TrendArrow";
import ScoreChart from "@/components/ScoreChart";
import { formatCount, formatDate, formatScore } from "@/lib/format";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ id: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  const channel = await getChannel(id);
  if (channel === NOT_FOUND || channel === null) {
    return { title: "Channel pacing" };
  }
  const score = channel.score ? formatScore(channel.score.score) : "—";
  return {
    title: `${channel.title} — channel pacing ${score}`,
    description: `Shot-pacing profile for ${channel.title}: per-video Staccato Scores over time.`,
  };
}

export default async function ChannelPage({ params }: Props) {
  const { id } = await params;
  const channel = await getChannel(id);

  if (channel === NOT_FOUND) notFound();

  if (channel === null) {
    return (
      <>
        <h1>Channel pacing</h1>
        <div className="notice">
          This channel&apos;s profile is temporarily unavailable &mdash; we
          couldn&apos;t reach the scoring service. Try again in a moment.
        </div>
        <Link href="/leaderboard">Back to the leaderboard</Link>
      </>
    );
  }

  const score = channel.score;
  const series = score?.series ?? [];
  const listed = series
    .slice()
    .sort((a, b) => {
      const ta = a.published_at ? Date.parse(a.published_at) : 0;
      const tb = b.published_at ? Date.parse(b.published_at) : 0;
      return tb - ta;
    });

  return (
    <>
      <p className="small faint mono" style={{ margin: 0 }}>
        channel{channel.category ? ` · ${channel.category}` : ""}
      </p>
      <h1 style={{ marginBottom: "0.15rem" }}>{channel.title}</h1>
      <p className="dim" style={{ marginTop: 0 }}>
        {channel.subscriber_count != null
          ? `${formatCount(channel.subscriber_count)} subscribers`
          : "subscriber count unavailable"}
      </p>

      {score ? (
        <>
          <div className="card" style={{ marginTop: "1.5rem" }}>
            <div className="scorePanel">
              <ScoreBadge
                score={score.score}
                label={labelForScore(score.score)}
                size="lg"
              />
              <div>
                <div style={{ fontSize: "1.1rem" }}>
                  <TrendArrow trend={score.trend} withText />
                </div>
                <div className="small dim" style={{ marginTop: "0.4rem" }}>
                  channel score across {score.n_videos} recent video
                  {score.n_videos === 1 ? "" : "s"}
                </div>
                <div className="small faint">
                  computed {formatDate(score.computed_at)} &middot; engine v
                  {score.engine_version}
                </div>
              </div>
            </div>
          </div>

          <h2>Per-video scores over time</h2>
          <div className="card" style={{ padding: "1rem" }}>
            <ScoreChart series={series} />
          </div>

          <h2>Videos</h2>
          <ul className="videoList">
            {listed.map((v) => (
              <li key={v.provider_video_id}>
                <span className="vTitle">
                  {v.title ?? v.provider_video_id}
                </span>
                <span className="vDate">{formatDate(v.published_at)}</span>
                <span
                  className="vScore"
                  style={{ color: labelColor(labelForScore(v.score)) }}
                >
                  {formatScore(v.score)}
                </span>
              </li>
            ))}
          </ul>
        </>
      ) : (
        <div className="notice">
          No pacing score yet for this channel &mdash; not enough measured
          videos.
        </div>
      )}

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
    </>
  );
}
