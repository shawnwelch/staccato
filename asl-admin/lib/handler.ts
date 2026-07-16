import { NextResponse } from "next/server";
import { backendFetch, BackendError } from "@/lib/api";

/**
 * Shared helper for route handlers: forward a POST to the backend admin API
 * and translate errors into a JSON shape the client components understand.
 */
export async function proxyPost(
  path: string,
  body?: unknown,
): Promise<NextResponse> {
  try {
    const data = await backendFetch<unknown>(path, {
      method: "POST",
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    return NextResponse.json(data);
  } catch (err) {
    // Backend 4xx (e.g. job not retryable) surfaces as-is; anything else is a 502.
    const status =
      err instanceof BackendError && err.status && err.status < 500
        ? err.status
        : 502;
    const message = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ ok: false, error: message }, { status });
  }
}
