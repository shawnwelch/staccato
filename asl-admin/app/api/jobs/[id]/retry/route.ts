import { NextResponse } from "next/server";
import { proxyPost } from "@/lib/handler";

export const dynamic = "force-dynamic";

export async function POST(
  _req: Request,
  ctx: { params: Promise<{ id: string }> },
) {
  const { id } = await ctx.params;
  if (!/^\d+$/.test(id)) {
    return NextResponse.json(
      { ok: false, error: "invalid job id" },
      { status: 400 },
    );
  }
  return proxyPost(`/admin/jobs/${id}/retry`);
}
