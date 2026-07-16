/**
 * Server-side client for the ASL backend admin API.
 *
 * SERVER ONLY. The ADMIN_API_TOKEN is attached here and only here; this
 * module must never be imported from a "use client" component. (We avoid the
 * `server-only` poison package to keep deps minimal — process.env.ADMIN_API_TOKEN
 * is not NEXT_PUBLIC_ so it is stripped from client bundles regardless.)
 */

const BACKEND_URL = (process.env.BACKEND_URL ?? "http://localhost:8000").replace(
  /\/+$/,
  "",
);

export class BackendError extends Error {
  constructor(
    message: string,
    public status?: number,
  ) {
    super(message);
    this.name = "BackendError";
  }
}

export async function backendFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const headers = new Headers(init?.headers);
  headers.set("Accept", "application/json");
  const token = process.env.ADMIN_API_TOKEN;
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init?.body != null) headers.set("Content-Type", "application/json");

  let res: Response;
  try {
    res = await fetch(`${BACKEND_URL}${path}`, {
      ...init,
      headers,
      cache: "no-store",
    });
  } catch (err) {
    throw new BackendError(
      `Backend unreachable at ${BACKEND_URL} (${err instanceof Error ? err.message : String(err)})`,
    );
  }

  if (!res.ok) {
    let detail = "";
    try {
      detail = (await res.text()).slice(0, 500);
    } catch {
      /* ignore */
    }
    throw new BackendError(
      `Backend responded ${res.status} for ${path}${detail ? `: ${detail}` : ""}`,
      res.status,
    );
  }
  return (await res.json()) as T;
}

/** Convenience wrapper for pages: resolves to data or an error message. */
export async function tryBackend<T>(
  path: string,
  init?: RequestInit,
): Promise<{ data: T; error: null } | { data: null; error: string }> {
  try {
    return { data: await backendFetch<T>(path, init), error: null };
  } catch (err) {
    return {
      data: null,
      error: err instanceof Error ? err.message : String(err),
    };
  }
}
