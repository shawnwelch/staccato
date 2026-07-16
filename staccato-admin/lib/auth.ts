import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

/**
 * Auth is OPTIONAL in dev: when the Clerk env vars are unset the app runs
 * open and the layout renders a "auth disabled — dev mode" banner.
 *
 * In production, set NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY and CLERK_SECRET_KEY
 * and drop Clerk's middleware in below. @clerk/nextjs is deliberately NOT a
 * hard dependency so local dev and CI builds never require it.
 */
export function isAuthConfigured(): boolean {
  return Boolean(
    process.env.CLERK_SECRET_KEY &&
      process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY,
  );
}

let warned = false;

/**
 * Middleware hook. Called from /middleware.ts for every matched request.
 *
 * TODO(clerk): to enable org-gated auth in production:
 *   1. `npm install @clerk/nextjs`
 *   2. Replace the body of this function (or middleware.ts itself) with:
 *
 *        import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
 *        export default clerkMiddleware(async (auth, req) => {
 *          const { userId, orgId } = await auth();
 *          if (!userId || orgId !== process.env.CLERK_ADMIN_ORG_ID) {
 *            // redirect to sign-in / render 403
 *          }
 *        });
 *
 *   3. Wrap app/layout.tsx children in <ClerkProvider>.
 *   See README.md "Enabling Clerk".
 */
export function authMiddleware(_req: NextRequest): NextResponse {
  if (!isAuthConfigured() && !warned) {
    warned = true;
    console.warn(
      "[staccato-admin] Clerk env vars unset — auth disabled, running in open dev mode. " +
        "Do NOT deploy like this.",
    );
  }
  if (isAuthConfigured() && !warned) {
    warned = true;
    console.warn(
      "[staccato-admin] Clerk env vars are set but Clerk middleware is not wired in " +
        "(see TODO(clerk) in lib/auth.ts). Requests are NOT being gated.",
    );
  }
  return NextResponse.next();
}
