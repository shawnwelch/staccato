import { ImageResponse } from "next/og";
import { getShare, NOT_FOUND, type PacingLabel } from "@/lib/api";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";
export const alt = "Staccato pacing score card";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

const LABEL_COLORS: Record<PacingLabel, string> = {
  calm: "#6ea8fe",
  moderate: "#2dd4bf",
  fast: "#f5b451",
  "hyper-paced": "#a78bfa",
};

export default async function OgImage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const data = await getShare(slug);

  const ok = data !== null && data !== NOT_FOUND;
  const analysis = ok ? data.analysis : null;
  const complete = analysis?.status === "complete" && analysis.score != null;

  const scoreText = complete ? String(Math.round(analysis!.score!)) : "…";
  const label = complete ? analysis!.label : null;
  const color = label ? LABEL_COLORS[label] : "#8b93a7";
  const title = (ok && data.video?.title) || "Pacing measurement";
  const channel = (ok && data.video?.channel_title) || "";
  const engine = analysis?.engine_version ?? "1.0.0";

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          background: "#0b0d12",
          color: "#e8eaf0",
          padding: "56px 64px",
          fontFamily: "sans-serif",
        }}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <div
            style={{
              fontSize: 34,
              fontWeight: 700,
              letterSpacing: 6,
              color: "#e8eaf0",
            }}
          >
            Staccato
          </div>
          <div style={{ fontSize: 24, color: "#5c6478" }}>
            see how fast anything cuts
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 56 }}>
          <div style={{ fontSize: 260, fontWeight: 700, color, lineHeight: 1 }}>
            {scoreText}
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 22 }}>
            {label ? (
              <div
                style={{
                  display: "flex",
                  alignSelf: "flex-start",
                  fontSize: 30,
                  letterSpacing: 3,
                  textTransform: "uppercase",
                  color,
                  border: `2px solid ${color}`,
                  borderRadius: 999,
                  padding: "8px 28px",
                }}
              >
                {label}
              </div>
            ) : (
              <div style={{ display: "flex", fontSize: 30, color: "#8b93a7" }}>
                measuring…
              </div>
            )}
            <div
              style={{
                display: "flex",
                fontSize: 40,
                fontWeight: 600,
                maxWidth: 700,
                lineHeight: 1.25,
              }}
            >
              {title.length > 80 ? `${title.slice(0, 77)}…` : title}
            </div>
            {channel ? (
              <div style={{ display: "flex", fontSize: 28, color: "#8b93a7" }}>
                {channel}
              </div>
            ) : null}
          </div>
        </div>

        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            fontSize: 22,
            color: "#5c6478",
          }}
        >
          <div style={{ display: "flex" }}>pacing intensity, 0–100</div>
          <div style={{ display: "flex" }}>engine v{engine}</div>
        </div>
      </div>
    ),
    { ...size },
  );
}
