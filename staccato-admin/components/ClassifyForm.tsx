"use client";

import { useState } from "react";

interface Result {
  channel_id: string;
  job_id: number;
}

export default function ClassifyForm() {
  const [channelUrl, setChannelUrl] = useState("");
  const [nVideos, setNVideos] = useState("20");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch("/api/classify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          channel_url: channelUrl,
          n_videos: nVideos === "" ? undefined : Number(nVideos),
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || data.error) {
        throw new Error(data.error || `HTTP ${res.status}`);
      }
      setResult(data as Result);
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
          <label htmlFor="channel_url">Channel URL</label>
          <input
            id="channel_url"
            type="url"
            required
            placeholder="https://www.youtube.com/@channel"
            value={channelUrl}
            onChange={(e) => setChannelUrl(e.target.value)}
            style={{ width: "100%" }}
          />
        </div>
        <div className="row">
          <label htmlFor="n_videos">Videos to analyze</label>
          <input
            id="n_videos"
            type="number"
            min={1}
            max={500}
            value={nVideos}
            onChange={(e) => setNVideos(e.target.value)}
            style={{ width: 90 }}
          />
        </div>
        <button className="primary" type="submit" disabled={busy}>
          {busy ? "Launching…" : "Launch classification"}
        </button>
      </form>

      {result && (
        <div className="notice ok">
          Classification launched for channel{" "}
          <code>{result.channel_id}</code> — coordinator job{" "}
          <strong>#{result.job_id}</strong>. Track the fan-out on the{" "}
          <a href={`/jobs?queue=batch`}>batch queue</a>.
        </div>
      )}
      {error && (
        <div className="notice error">
          <strong>Launch failed.</strong> {error}
        </div>
      )}
    </>
  );
}
