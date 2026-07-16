# staccato-frontend

Public web app for Staccato — the video shot-pacing scorer. Share pages, channel
profiles, and a leaderboard. All data is read from the `staccato-backend` public
API; this app has no database of its own.

## Stack

**Next.js 15 (App Router) + TypeScript + React 19, plain CSS.**

Why: the growth surfaces (share pages, leaderboard) need server-rendered HTML
with per-page metadata and OpenGraph images so links unfurl with the score
visible — Next's App Router gives us `generateMetadata` and
`opengraph-image.tsx` (via `next/og`) out of the box, plus a single Node
process that deploys cleanly on Render. No CSS framework or chart library:
one global stylesheet and a hand-rolled server-rendered SVG chart keep the
dependency count at three runtime packages (`next`, `react`, `react-dom`).

All pages are dynamically rendered (`force-dynamic`) with 60s fetch
revalidation, so `next build` succeeds without a live backend and pages fail
soft (a "temporarily unavailable" notice) when the backend is unreachable.

## Environment variables

| Variable                  | Purpose                                     | Default                 |
| ------------------------- | ------------------------------------------- | ----------------------- |
| `BACKEND_URL`             | Backend API base URL (server-side fetches)  | `http://localhost:8000` |
| `NEXT_PUBLIC_BACKEND_URL` | Same URL, exposed to client-side code       | `http://localhost:8000` |
| `PORT`                    | Port for `next start` (set by Render)       | `3000`                  |

Copy `.env.example` to `.env.local` for local development.

## Development

```sh
npm install
npm run dev        # http://localhost:3000, expects backend on :8000
```

## Build & production

```sh
npm run build
npm start          # binds to $PORT (defaults to 3000)
```

## Deploy on Render

Deployed as a standard **Node web service** (configured in the repo-root
`render.yaml`):

- Root directory: `staccato-frontend`
- Build command: `npm install && npm run build`
- Start command: `npm start` (binds to Render's `$PORT`)
- Env vars: set `BACKEND_URL` and `NEXT_PUBLIC_BACKEND_URL` to the deployed
  backend URL.

## Pages

- `/` — landing (neutral pitch, sample score card, CTAs)
- `/s/[slug]` — public share page for one analysis (score, heat map, stats,
  OpenGraph card via `opengraph-image.tsx`)
- `/channels/[id]` — channel profile (score, trend, per-video SVG chart)
- `/leaderboard` — ranked channels with category filter + pagination
- `/methodology` — what the score measures, versioning promise
