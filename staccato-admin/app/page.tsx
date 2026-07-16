import Link from "next/link";
import { tryBackend } from "@/lib/api";
import type { JobStats } from "@/lib/types";
import { JOB_STATUSES } from "@/lib/types";
import ErrorNotice from "@/components/ErrorNotice";

export const dynamic = "force-dynamic";

const QUICK_LINKS = [
  {
    href: "/jobs?status=failed",
    title: "Failed jobs",
    sub: "Inspect and retry failures",
  },
  {
    href: "/classify",
    title: "Classify a channel",
    sub: "Fan out analyze jobs for a channel",
  },
  {
    href: "/moderation",
    title: "Moderation queue",
    sub: "Review optical live-session scans",
  },
  {
    href: "/engine",
    title: "Engine rollout",
    sub: "Score distributions and re-scoring",
  },
];

export default async function DashboardPage() {
  const { data: stats, error } = await tryBackend<JobStats>("/admin/jobs/stats");

  return (
    <>
      <h1>Dashboard</h1>
      <p className="page-desc">
        Procrastinate job queue health for the Staccato pacing scorer.
      </p>

      {error && <ErrorNotice message={error} />}

      {stats && (
        <>
          <h2>Jobs by status</h2>
          <div className="cards">
            {JOB_STATUSES.map((status) => (
              <div className="card" key={status}>
                <div className="label">
                  <span className={`pill ${status}`}>{status}</span>
                </div>
                <div className="value">{stats.by_status[status] ?? 0}</div>
              </div>
            ))}
          </div>

          <h2>Jobs by queue</h2>
          {Object.keys(stats.by_queue).length === 0 ? (
            <div className="panel empty">No queues reported.</div>
          ) : (
            <table className="data" style={{ maxWidth: 480 }}>
              <thead>
                <tr>
                  <th>Queue</th>
                  <th className="num">Jobs</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(stats.by_queue)
                  .sort((a, b) => b[1] - a[1])
                  .map(([queue, count]) => (
                    <tr key={queue}>
                      <td className="mono">{queue}</td>
                      <td className="num">{count}</td>
                      <td>
                        <Link href={`/jobs?queue=${encodeURIComponent(queue)}`}>
                          view
                        </Link>
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          )}
        </>
      )}

      <h2>Quick links</h2>
      <div className="quick-links">
        {QUICK_LINKS.map((l) => (
          <Link key={l.href} href={l.href}>
            <div className="title">{l.title}</div>
            <div className="sub">{l.sub}</div>
          </Link>
        ))}
      </div>
    </>
  );
}
