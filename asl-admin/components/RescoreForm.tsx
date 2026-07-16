"use client";

import { useState } from "react";

export default function RescoreForm({ versions }: { versions: string[] }) {
  const [fromVersion, setFromVersion] = useState(versions[0] ?? "");
  const [dryRun, setDryRun] = useState(true);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<{
    enqueued: number;
    dryRun: boolean;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch("/api/rescore", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          from_engine_version: fromVersion,
          dry_run: dryRun,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || data.error) {
        throw new Error(data.error || `HTTP ${res.status}`);
      }
      setResult({ enqueued: data.enqueued as number, dryRun });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <form className="panel form" onSubmit={submit}>
        <div className="row">
          <label htmlFor="from_version">Re-score videos scored by engine</label>
          {versions.length > 0 ? (
            <select
              id="from_version"
              value={fromVersion}
              onChange={(e) => setFromVersion(e.target.value)}
            >
              {versions.map((v) => (
                <option key={v} value={v}>
                  {v}
                </option>
              ))}
            </select>
          ) : (
            <input
              id="from_version"
              type="text"
              required
              placeholder="e.g. 0.9.2"
              value={fromVersion}
              onChange={(e) => setFromVersion(e.target.value)}
            />
          )}
        </div>
        <div className="row check">
          <input
            id="dry_run"
            type="checkbox"
            checked={dryRun}
            onChange={(e) => setDryRun(e.target.checked)}
          />
          <label htmlFor="dry_run">
            Dry run — count affected videos, enqueue nothing
          </label>
        </div>
        <button
          className={dryRun ? "primary" : "danger"}
          type="submit"
          disabled={busy || !fromVersion}
        >
          {busy
            ? "Submitting…"
            : dryRun
              ? "Run dry run"
              : "Enqueue re-score jobs"}
        </button>
      </form>

      {result && (
        <div className="notice ok">
          {result.dryRun ? (
            <>
              Dry run: <strong>{result.enqueued}</strong> video
              {result.enqueued === 1 ? "" : "s"} scored by{" "}
              <code>{fromVersion}</code> would be re-scored. Nothing was
              enqueued.
            </>
          ) : (
            <>
              Enqueued <strong>{result.enqueued}</strong> re-score job
              {result.enqueued === 1 ? "" : "s"} for videos scored by{" "}
              <code>{fromVersion}</code>. Watch progress on the{" "}
              <a href="/jobs?queue=batch">jobs page</a>.
            </>
          )}
        </div>
      )}
      {error && (
        <div className="notice error">
          <strong>Re-score request failed.</strong> {error}
        </div>
      )}
    </>
  );
}
