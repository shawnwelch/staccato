"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function RetryButton({ jobId }: { jobId: number }) {
  const router = useRouter();
  const [state, setState] = useState<"idle" | "busy" | "done" | "error">(
    "idle",
  );
  const [error, setError] = useState<string | null>(null);

  async function retry() {
    setState("busy");
    setError(null);
    try {
      const res = await fetch(`/api/jobs/${jobId}/retry`, { method: "POST" });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || data.ok === false) {
        throw new Error(data.error || `HTTP ${res.status}`);
      }
      setState("done");
      router.refresh();
    } catch (err) {
      setState("error");
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  if (state === "done") {
    return <span className="pill todo">re-enqueued</span>;
  }

  return (
    <>
      <button
        className="small"
        onClick={retry}
        disabled={state === "busy"}
        title="Re-enqueue this failed job"
      >
        {state === "busy" ? "retrying…" : "retry"}
      </button>
      {state === "error" && (
        <span
          style={{ color: "var(--danger)", fontSize: 11, marginLeft: 6 }}
          title={error ?? undefined}
        >
          failed
        </span>
      )}
    </>
  );
}
