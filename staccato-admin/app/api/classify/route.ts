import { NextResponse } from "next/server";
import { proxyPost } from "@/lib/handler";

export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  let body: { channel_url?: unknown; n_videos?: unknown };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json(
      { ok: false, error: "invalid JSON body" },
      { status: 400 },
    );
  }

  const channelUrl = typeof body.channel_url === "string" ? body.channel_url.trim() : "";
  if (!channelUrl) {
    return NextResponse.json(
      { ok: false, error: "channel_url is required" },
      { status: 400 },
    );
  }
  let nVideos = 20;
  if (body.n_videos !== undefined && body.n_videos !== null && body.n_videos !== "") {
    nVideos = Number(body.n_videos);
    if (!Number.isInteger(nVideos) || nVideos < 1 || nVideos > 500) {
      return NextResponse.json(
        { ok: false, error: "n_videos must be an integer between 1 and 500" },
        { status: 400 },
      );
    }
  }

  return proxyPost("/admin/channels/classify", {
    channel_url: channelUrl,
    n_videos: nVideos,
  });
}
