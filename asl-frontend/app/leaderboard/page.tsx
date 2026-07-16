import type { Metadata } from "next";
import Link from "next/link";
import { getLeaderboard, labelForScore } from "@/lib/api";
import { NOT_FOUND } from "@/lib/api";
import { labelColor } from "@/components/ScoreBadge";
import TrendArrow from "@/components/TrendArrow";
import { formatCount, formatScore } from "@/lib/format";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Channel leaderboard",
  description:
    "Channels ranked by shot-pacing intensity, as measured by ASL. Filter by category.",
};

const PAGE_SIZE = 25;

type Search = { category?: string; page?: string; order?: string };

function href(next: Partial<Search>, current: Search): string {
  const merged = { ...current, ...next };
  const qs = new URLSearchParams();
  if (merged.category) qs.set("category", merged.category);
  if (merged.page && merged.page !== "1") qs.set("page", merged.page);
  if (merged.order && merged.order !== "desc") qs.set("order", merged.order);
  const s = qs.toString();
  return s ? `/leaderboard?${s}` : "/leaderboard";
}

export default async function LeaderboardPage({
  searchParams,
}: {
  searchParams: Promise<Search>;
}) {
  const sp = await searchParams;
  const page = Math.max(1, Number.parseInt(sp.page ?? "1", 10) || 1);
  const order = sp.order === "asc" ? "asc" : "desc";
  const category = sp.category || undefined;

  const data = await getLeaderboard({
    category,
    page,
    pageSize: PAGE_SIZE,
    order,
  });

  if (data === null || data === NOT_FOUND) {
    return (
      <>
        <h1>Channel leaderboard</h1>
        <div className="notice">
          The leaderboard is temporarily unavailable &mdash; we couldn&apos;t
          reach the scoring service. Try again in a moment.
        </div>
      </>
    );
  }

  const totalPages = Math.max(1, Math.ceil(data.total / data.page_size));
  const current: Search = {
    category,
    page: String(page),
    order,
  };

  return (
    <>
      <h1>Channel leaderboard</h1>
      <p className="lede" style={{ fontSize: "1rem" }}>
        Channels ranked by pacing intensity &mdash; how fast their recent
        videos cut. {order === "desc" ? "Fastest" : "Calmest"} first.{" "}
        <Link href={href({ order: order === "desc" ? "asc" : "desc", page: "1" }, current)}>
          Flip order
        </Link>
      </p>

      {data.categories.length > 0 && (
        <div className="filterRow">
          <Link
            className={`filterChip${!category ? " active" : ""}`}
            href={href({ category: "", page: "1" }, current)}
          >
            All
          </Link>
          {data.categories.map((c) => (
            <Link
              key={c}
              className={`filterChip${category === c ? " active" : ""}`}
              href={href({ category: c, page: "1" }, current)}
            >
              {c}
            </Link>
          ))}
        </div>
      )}

      <div className="tableWrap">
        <table>
          <thead>
            <tr>
              <th className="num">#</th>
              <th>Channel</th>
              <th>Category</th>
              <th className="num">Subs</th>
              <th className="num">Score</th>
              <th>Pacing</th>
              <th>Trend</th>
              <th className="num">Videos</th>
            </tr>
          </thead>
          <tbody>
            {data.items.length === 0 && (
              <tr>
                <td colSpan={8} className="dim" style={{ textAlign: "center" }}>
                  No channels{category ? ` in ${category}` : ""} yet.
                </td>
              </tr>
            )}
            {data.items.map((item) => {
              const label = labelForScore(item.score);
              const color = labelColor(label);
              return (
                <tr key={item.channel_id}>
                  <td className="num faint">{item.rank}</td>
                  <td>
                    <Link href={`/channels/${encodeURIComponent(item.channel_id)}`}>
                      {item.title}
                    </Link>
                  </td>
                  <td className="dim">{item.category ?? "—"}</td>
                  <td className="num dim">{formatCount(item.subscriber_count)}</td>
                  <td className="num" style={{ color, fontWeight: 700 }}>
                    {formatScore(item.score)}
                  </td>
                  <td>
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
                  </td>
                  <td>
                    <TrendArrow trend={item.trend} />
                  </td>
                  <td className="num dim">{item.n_videos}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="pager">
        {page > 1 ? (
          <Link href={href({ page: String(page - 1) }, current)}>
            &larr; Previous
          </Link>
        ) : (
          <span className="disabled">&larr; Previous</span>
        )}
        <span className="dim">
          Page {data.page} of {totalPages} &middot; {data.total} channels
        </span>
        {page < totalPages ? (
          <Link href={href({ page: String(page + 1) }, current)}>
            Next &rarr;
          </Link>
        ) : (
          <span className="disabled">Next &rarr;</span>
        )}
      </div>
    </>
  );
}
