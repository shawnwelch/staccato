"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function ModerationActions({ sessionId }: { sessionId: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState<"promote" | "reject" | null>(null);
  const [done, setDone] = useState<"promoted" | "rejected" | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function act(action: "promote" | "reject") {
    setBusy(action);
    setError(null);
    try {
      const res = await fetch(
        `/api/live-sessions/${encodeURIComponent(sessionId)}/${action}`,
        { method: "POST" },
      );
      const data = await res.json().catch(() => ({}));
      if (!res.ok || data.ok === false) {
        throw new Error(data.error || `HTTP ${res.status}`);
      }
      setDone(action === "promote" ? "promoted" : "rejected");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  if (done === "promoted") return <span className="pill succeeded">promoted</span>;
  if (done === "rejected") return <span className="pill cancelled">rejected</span>;

  return (
    <span style={{ whiteSpace: "nowrap" }}>
      <button
        className="small primary"
        disabled={busy !== null}
        onClick={() => act("promote")}
        title="Merge this scan into canonical score pools"
      >
        {busy === "promote" ? "…" : "promote"}
      </button>{" "}
      <button
        className="small danger"
        disabled={busy !== null}
        onClick={() => act("reject")}
        title="Discard this scan"
      >
        {busy === "reject" ? "…" : "reject"}
      </button>
      {error && (
        <span
          style={{ color: "var(--danger)", fontSize: 11, marginLeft: 6 }}
          title={error}
        >
          failed
        </span>
      )}
    </span>
  );
}
