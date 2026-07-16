import type { NextRequest } from "next/server";
import { authMiddleware } from "@/lib/auth";

// Thin shim: all auth logic lives in lib/auth.ts (see TODO(clerk) there for
// the Clerk drop-in point).
export function middleware(req: NextRequest) {
  return authMiddleware(req);
}

export const config = {
  // Everything except Next.js internals and static assets.
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
