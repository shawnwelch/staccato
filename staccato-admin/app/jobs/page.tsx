import Link from "next/link";
import { tryBackend } from "@/lib/api";
import type { Job, Paginated } from "@/lib/types";
import { JOB_STATUSES } from "@/lib/types";
import ErrorNotice from "@/components/ErrorNotice";
import RetryButton from "@/components/RetryButton";

export const dynamic = "force-dynamic";

const PAGE_SIZE = 50;

type Search = {
  status?: string;
  queue?: string;
  task?: string;
  page?: string;
};

function buildQuery(params: Search, page: number): string {
  const qs = new URLSearchParams();
  if (params.status) qs.set("status", params.status);
  if (params.queue) qs.set("queue", params.queue);
  if (params.task) qs.set("task", params.task);
  qs.set("page", String(page));
  qs.set("page_size", String(PAGE_SIZE));
  return qs.toString();
}

function pageHref(params: Search, page: number): string {
  const qs = new URLSearchParams();
  if (params.status) qs.set("status", params.status);
  if (params.queue) qs.set("queue", params.queue);
  if (params.task) qs.set("task", params.task);
  if (page > 1) qs.set("page", String(page));
  const s = qs.toString();
  return s ? `/jobs?${s}` : "/jobs";
}

function truncateArgs(args: Record<string, unknown>): string {
  const s = JSON.stringify(args);
  return s.length > 60 ? `${s.slice(0, 60)}…` : s;
}

export default async function JobsPage({
  searchParams,
}: {
  searchParams: Promise<Search>;
}) {
  const params = await searchParams;
  const page = Math.max(1, Number(params.page) || 1);

  const { data, error } = await tryBackend<Paginated<Job>>(
    `/admin/jobs?${buildQuery(params, page)}`,
  );

  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  return (
    <>
      <h1>Jobs</h1>
      <p className="page-desc">
        Procrastinate jobs across all queues. Failed jobs can be re-enqueued
        with retry.
      </p>

      <form className="filters" method="get" action="/jobs">
        <div>
          <label htmlFor="status">Status</label>
          <select id="status" name="status" defaultValue={params.status ?? ""}>
            <option value="">all</option>
            {JOB_STATUSES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="queue">Queue</label>
          <input
            id="queue"
            name="queue"
            type="text"
            placeholder="e.g. batch"
            defaultValue={params.queue ?? ""}
            size={14}
          />
        </div>
        <div>
          <label htmlFor="task">Task</label>
          <input
            id="task"
            name="task"
            type="text"
            placeholder="task name"
            defaultValue={params.task ?? ""}
            size={22}
          />
        </div>
        <button type="submit">Filter</button>
        <Link className="btn" href="/jobs" style={{ padding: "4px 8px" }}>
          reset
        </Link>
      </form>

      {error && <ErrorNotice message={error} />}

      {data && (
        <>
          <table className="data">
            <thead>
              <tr>
                <th className="num">ID</th>
                <th>Status</th>
                <th>Queue</th>
                <th>Task</th>
                <th className="num">Pri</th>
                <th className="num">Att</th>
                <th>Scheduled</th>
                <th>Args</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {data.items.length === 0 && (
                <tr>
                  <td colSpan={9} className="empty">
                    No jobs match the current filters.
                  </td>
                </tr>
              )}
              {data.items.map((job) => (
                <tr key={job.id}>
                  <td className="num">{job.id}</td>
                  <td>
                    <span className={`pill ${job.status}`}>{job.status}</span>
                  </td>
                  <td className="mono">{job.queue_name}</td>
                  <td className="mono">{job.task_name}</td>
                  <td className="num">{job.priority}</td>
                  <td className="num">{job.attempts}</td>
                  <td className="mono">
                    {job.scheduled_at
                      ? job.scheduled_at.replace("T", " ").slice(0, 19)
                      : "—"}
                  </td>
                  <td>
                    <details className="args">
                      <summary>{truncateArgs(job.args)}</summary>
                      <pre>{JSON.stringify(job.args, null, 2)}</pre>
                    </details>
                  </td>
                  <td>
                    {job.status === "failed" && <RetryButton jobId={job.id} />}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="pager">
            {page > 1 ? (
              <Link href={pageHref(params, page - 1)}>← prev</Link>
            ) : (
              <span>← prev</span>
            )}
            <span>
              page {data.page} of {totalPages}
            </span>
            {page < totalPages ? (
              <Link href={pageHref(params, page + 1)}>next →</Link>
            ) : (
              <span>next →</span>
            )}
            <span className="spacer" />
            <span>{data.total} total</span>
          </div>
        </>
      )}
    </>
  );
}
