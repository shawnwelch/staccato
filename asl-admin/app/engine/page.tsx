import { tryBackend } from "@/lib/api";
import type { EngineInfo } from "@/lib/types";
import ErrorNotice from "@/components/ErrorNotice";
import RescoreForm from "@/components/RescoreForm";

export const dynamic = "force-dynamic";

function fmt(v: number | null): string {
  return v === null || v === undefined ? "—" : v.toFixed(1);
}

export default async function EnginePage() {
  const { data, error } = await tryBackend<EngineInfo>("/admin/engine/info");

  const staleVersions = data
    ? data.distributions
        .map((d) => d.engine_version)
        .filter((v) => v !== data.current_version)
    : [];

  return (
    <>
      <h1>Engine rollout</h1>
      <p className="page-desc">
        The scoring engine turns detected cuts into a 0–100 pacing score from
        median shot length. Engine releases can shift scores, so every stored
        score is stamped with the engine version that produced it. Use this
        page to see how many scores each version produced and to roll old
        versions forward.
      </p>

      {error && (
        <>
          <ErrorNotice message={error} />
          <h2>Re-score rollout</h2>
          <div className="notice warn">
            <strong>Published scores are never silently rescored.</strong>{" "}
            Stats are unavailable, but you can still submit a re-score by
            typing the source engine version. Always dry-run first.
          </div>
          <RescoreForm versions={[]} />
        </>
      )}

      {data && (
        <>
          <div className="cards">
            <div className="card">
              <div className="label">Current engine version</div>
              <div className="value">{data.current_version}</div>
            </div>
            <div className="card">
              <div className="label">Versions with stored scores</div>
              <div className="value">{data.distributions.length}</div>
            </div>
          </div>

          <h2>Score distribution by engine version</h2>
          {data.distributions.length === 0 ? (
            <div className="panel empty">No scored videos yet.</div>
          ) : (
            <table className="data" style={{ maxWidth: 640 }}>
              <thead>
                <tr>
                  <th>Engine version</th>
                  <th className="num">Scores</th>
                  <th className="num">Mean</th>
                  <th className="num">Median</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {data.distributions.map((d) => (
                  <tr key={d.engine_version}>
                    <td className="mono">{d.engine_version}</td>
                    <td className="num">{d.count}</td>
                    <td className="num">{fmt(d.mean_score)}</td>
                    <td className="num">{fmt(d.median_score)}</td>
                    <td>
                      {d.engine_version === data.current_version && (
                        <span className="pill succeeded">current</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <h2>Re-score rollout</h2>
          <div className="notice warn">
            <strong>Published scores are never silently rescored.</strong>{" "}
            This tool is the only path that re-runs the current engine over
            already-published scores, and each run is an explicit, audited
            operator action. Always dry-run first to see the blast radius; a
            live run enqueues one re-score job per affected video on the batch
            queue.
          </div>
          <RescoreForm versions={staleVersions} />
        </>
      )}
    </>
  );
}
