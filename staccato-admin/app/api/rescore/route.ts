import { NextResponse } from "next/server";
import { proxyPost } from "@/lib/handler";

export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  let body: { from_engine_version?: unknown; dry_run?: unknown };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json(
      { ok: false, error: "invalid JSON body" },
      { status: 400 },
    );
  }

  const fromVersion =
    typeof body.from_engine_version === "string"
      ? body.from_engine_version.trim()
      : "";
  if (!fromVersion) {
    return NextResponse.json(
      { ok: false, error: "from_engine_version is required" },
      { status: 400 },
    );
  }

  return proxyPost("/admin/rescore", {
    from_engine_version: fromVersion,
    dry_run: Boolean(body.dry_run),
  });
}
