import { NextResponse } from "next/server";
import { proxyPost } from "@/lib/handler";

export const dynamic = "force-dynamic";

export async function POST(
  _req: Request,
  ctx: { params: Promise<{ id: string; action: string }> },
) {
  const { id, action } = await ctx.params;
  if (action !== "promote" && action !== "reject") {
    return NextResponse.json(
      { ok: false, error: "action must be promote or reject" },
      { status: 400 },
    );
  }
  if (!/^[A-Za-z0-9_-]+$/.test(id)) {
    return NextResponse.json(
      { ok: false, error: "invalid session id" },
      { status: 400 },
    );
  }
  return proxyPost(`/admin/live-sessions/${encodeURIComponent(id)}/${action}`);
}
