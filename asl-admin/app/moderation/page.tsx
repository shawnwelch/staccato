import Link from "next/link";
import { tryBackend } from "@/lib/api";
import type { LiveSession, Paginated } from "@/lib/types";
import ErrorNotice from "@/components/ErrorNotice";
import ModerationActions from "@/components/ModerationActions";

export const dynamic = "force-dynamic";

const DELTA_FLAG_THRESHOLD = 5;

function fmtScore(v: number | null): string {
  return v === null || v === undefined ? "—" : v.toFixed(1);
}

function delta(s: LiveSession): number | null {
  if (s.device_score === null || s.device_score === undefined) return null;
  return Math.abs(s.device_score - s.recomputed_score);
}

export default async function ModerationPage({
  searchParams,
}: {
  searchParams: Promise<{ page?: string }>;
}) {
  const params = await searchParams;
  const page = Math.max(1, Number(params.page) || 1);

  const { data, error } = await tryBackend<Paginated<LiveSession>>(
    `/admin/live-sessions?promoted=false&page=${page}`,
  );

  const pending = data ? data.items.filter((s) => !s.reviewed) : [];
  const pageSize = data?.page_size || 50;
  const totalPages = data ? Math.max(1, Math.ceil(data.total / pageSize)) : 1;

  return (
    <>
      <h1>Optical scan moderation</h1>
      <p className="page-desc">
        Live sessions scored on-device by pointing a camera at a screen.
        Camera-derived numbers are noisier than source-accurate analysis, so
        the server recomputes each score from the uploaded cut timeline —
        nothing is merged into canonical score pools until a human promotes
        it here. Rows where device and recomputed scores differ by more than{" "}
        {DELTA_FLAG_THRESHOLD} points are flagged; treat the recomputed score
        as authoritative.
      </p>

      {error && <ErrorNotice message={error} />}

      {data && (
        <>
          <table className="data">
            <thead>
              <tr>
                <th>Session</th>
                <th>User</th>
                <th>Content</th>
                <th className="num">Duration</th>
                <th className="num">Cuts</th>
                <th className="num">Device score</th>
                <th className="num">Recomputed</th>
                <th className="num">Δ</th>
                <th>Label</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {pending.length === 0 && (
                <tr>
                  <td colSpan={11} className="empty">
                    Moderation queue is empty — no unreviewed sessions on this
                    page.
                  </td>
                </tr>
              )}
              {pending.map((s) => {
                const d = delta(s);
                const flagged = d !== null && d > DELTA_FLAG_THRESHOLD;
                return (
                  <tr key={s.id} className={flagged ? "flagged" : undefined}>
                    <td className="mono" title={s.id}>
                      {s.id.length > 12 ? `${s.id.slice(0, 12)}…` : s.id}
                    </td>
                    <td className="mono" title={s.user_id}>
                      {s.user_id.length > 12
                        ? `${s.user_id.slice(0, 12)}…`
                        : s.user_id}
                    </td>
                    <td>{s.content_label}</td>
                    <td className="num">{s.duration_s.toFixed(0)}s</td>
                    <td className="num">{s.cut_count}</td>
                    <td className="num">{fmtScore(s.device_score)}</td>
                    <td className="num">{fmtScore(s.recomputed_score)}</td>
                    <td className="num">
                      {d === null ? (
                        "—"
                      ) : flagged ? (
                        <span
                          className="delta-flag"
                          title={`Device and recomputed scores differ by ${d.toFixed(1)} points (> ${DELTA_FLAG_THRESHOLD})`}
                        >
                          {d.toFixed(1)} ⚑
                        </span>
                      ) : (
                        d.toFixed(1)
                      )}
                    </td>
                    <td>{s.label}</td>
                    <td className="mono">
                      {s.created_at.replace("T", " ").slice(0, 16)}
                    </td>
                    <td>
                      <ModerationActions sessionId={s.id} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          <div className="pager">
            {page > 1 ? (
              <Link href={`/moderation?page=${page - 1}`}>← prev</Link>
            ) : (
              <span>← prev</span>
            )}
            <span>
              page {page} of {totalPages}
            </span>
            {page < totalPages ? (
              <Link href={`/moderation?page=${page + 1}`}>next →</Link>
            ) : (
              <span>next →</span>
            )}
            <span className="spacer" />
            <span>
              {pending.length} pending on this page · {data.total} unpromoted
              total
            </span>
          </div>

          <div className="notice">
            <strong>Promotion is the merge gate.</strong> Promoting a session
            merges its recomputed score into the canonical pools used for
            channel and content aggregates. Rejecting discards the scan.
            Optical scans are never merged without this review.
          </div>
        </>
      )}
    </>
  );
}
