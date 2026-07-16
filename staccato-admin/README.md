# staccato-admin

Internal ops web app for the Staccato video pacing scorer. Next.js 15 (App
Router) + TypeScript, plain CSS, no UI framework. Talks to the FastAPI
backend's `/admin` API (Procrastinate job queue, optical-scan moderation,
engine rollout tooling).

**Internal-only.** In production this app is Clerk org-gated; in dev it can
run open (a warning banner is shown).

## Pages

| Route         | Purpose                                                                 |
| ------------- | ----------------------------------------------------------------------- |
| `/`           | Job stats by status, queue breakdown, quick links                        |
| `/jobs`       | Job table with status/queue/task filters, pagination, retry for failures |
| `/classify`   | Launch channel classification (fans out analyze jobs on the batch queue) |
| `/moderation` | Review optical live-session scans; promote/reject before canonical merge |
| `/engine`     | Engine version score distributions and re-score rollout (with dry run)   |

## Environment variables

| Var                                 | Required | Purpose                                                                 |
| ----------------------------------- | -------- | ------------------------------------------------------------------------ |
| `BACKEND_URL`                       | yes      | Base URL of the FastAPI backend, e.g. `http://localhost:8000`             |
| `ADMIN_API_TOKEN`                   | yes      | Bearer token for `/admin` calls. Attached **server-side only** (route handlers / server components); never shipped to the browser. |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | prod     | Clerk publishable key                                                     |
| `CLERK_SECRET_KEY`                  | prod     | Clerk secret key                                                          |

Copy `.env.example` to `.env.local` and fill in values.

## Dev

```bash
npm install
npm run dev        # http://localhost:3100
```

With the Clerk vars unset the app runs open and shows an
"auth disabled — dev mode" banner. Pages that need the backend render a
graceful error notice when it is unreachable.

## Build / production

```bash
npm run build
npm start
```

All data pages are `force-dynamic`, so the build never needs the backend to
be reachable.

## Enabling Clerk (production)

`@clerk/nextjs` is intentionally **not** a hard dependency so dev installs
and CI builds never require it. To enable org gating:

1. `npm install @clerk/nextjs`
2. Set `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` and `CLERK_SECRET_KEY` (and your
   org id, e.g. `CLERK_ADMIN_ORG_ID`).
3. Replace the `TODO(clerk)` hook in `lib/auth.ts` (or `middleware.ts`
   directly) with `clerkMiddleware`, gating on membership of the ops org:

   ```ts
   import { clerkMiddleware } from "@clerk/nextjs/server";

   export default clerkMiddleware(async (auth, req) => {
     const { userId, orgId, redirectToSignIn } = await auth();
     if (!userId) return redirectToSignIn();
     if (orgId !== process.env.CLERK_ADMIN_ORG_ID) {
       return new Response("Forbidden", { status: 403 });
     }
   });
   ```

4. Wrap the children in `app/layout.tsx` with `<ClerkProvider>`.

Until that drop-in is done, setting the Clerk vars only removes the dev
banner — a startup warning reminds you requests are not actually gated.

## Backend API used

All under `${BACKEND_URL}/admin`, authenticated with
`Authorization: Bearer ${ADMIN_API_TOKEN}`:

- `GET /admin/jobs`, `GET /admin/jobs/stats`, `POST /admin/jobs/{id}/retry`
- `POST /admin/channels/classify`
- `GET /admin/live-sessions`, `POST /admin/live-sessions/{id}/promote`,
  `POST /admin/live-sessions/{id}/reject`
- `GET /admin/engine/info`, `POST /admin/rescore`

The browser never calls the backend directly — client components post to
Next.js route handlers under `/api/*`, which proxy server-side with the
token.

## Deploying on Render

Create a **Web Service** from this directory (`staccato-admin` as root):

- Build command: `npm install && npm run build`
- Start command: `npm start` (binds port 3100; set Render's `PORT` by
  changing the start script or use `next start -p $PORT`)
- Environment: Node 22; set `BACKEND_URL` to the backend's internal Render
  URL, plus `ADMIN_API_TOKEN` and the Clerk vars.

Since this is internal tooling, keep it off public search (Render's
`X-Robots-Tag` or Clerk gating) and never expose `ADMIN_API_TOKEN` as a
`NEXT_PUBLIC_` var.
