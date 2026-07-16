# staccato

Monorepo for **Staccato** — a pacing scorer for video: paste a URL
(or point a phone camera at a screen) and get a 0–100 **pacing intensity
score** plus a timeline heat map of cut density. A light meter for video
pacing: it reports what it measures, with neutral labels
(calm / moderate / fast / hyper-paced), and makes no claims about what pacing
does to anyone.

## Layout

| Directory | What it is | Stack |
|---|---|---|
| [`staccato-backend/`](staccato-backend/) | API + workers + the scoring engine | Python 3.12, FastAPI, SQLAlchemy 2, Procrastinate, PySceneDetect |
| [`staccato-apple`](https://github.com/shawnwelch/staccato-apple) | iOS app (flagship surface) — separate repo | SwiftUI, iOS 26 SDK, Swift 6, StoreKit 2 |
| [`staccato-frontend/`](staccato-frontend/) | Public web: share pages, channels, leaderboard | Next.js 15 (App Router), TypeScript |
| [`staccato-admin/`](staccato-admin/) | Internal ops: jobs, moderation, engine rollout | Next.js 15 (App Router), TypeScript |
| [`fixtures/`](fixtures/) | Shared golden test vectors pinning the engine math | JSON |

Shared infrastructure: **Clerk** (auth, all surfaces), **Neon** Postgres
(one DB; Procrastinate manages its own schema), **Render** (backend web +
worker + cron, both frontends), **Cloudflare R2** (heat map PNGs + result
JSON; S3-compatible via boto3). See `render.yaml`.

## The engine, in one paragraph

`staccato-backend/staccato_backend/engine/` is a dependency-light module (open-core;
no imports from app code) with three primitives: `detect_cuts` (PySceneDetect
ContentDetector), `build_heatmap` (centered rolling window → cuts/min), and
`pacing_score` — a logistic curve on **median** shot length:
`100 / (1 + (median / 11.0) ** 1.3)`. Anchors: 34s → ~19, 11s → 50, 3s → ~84,
1.5s → ~93. The formula is product surface area: every stored score carries
`engine_version` (currently **1.0.0**), and scores are never silently
rescored. `fixtures/golden_vectors.json` pins the math bit-for-bit across the
Python engine and the Swift port (`PacingKit`), which now lives in
[shawnwelch/staccato-apple](https://github.com/shawnwelch/staccato-apple) but
is still pinned by this same fixture: both test suites consume byte-identical
copies of `fixtures/golden_vectors.json`.

## Product rules that shape the code

- **3 free URL scans, lifetime, enforced server-side** with a row-locked
  counter (`deps/entitlements.py` — the only place gating lives). Dedupe runs
  before gating: a video already scored at the current engine version returns
  instantly and burns no credit.
- **$9.99/month** (Apple IAP via StoreKit 2; `entitlements.source` is a
  column, so Stripe web checkout later is data, not a migration).
- **Live capture is on-device** — no video leaves the phone. The backend
  recomputes scores from submitted cut times and quarantines optical scans
  from canonical scores until moderated in staccato-admin.
- **Positioning:** the tool is an instrument. Copy says what it measures,
  never what it does to anyone. Labels, never judgments.

## Quick start

```bash
# Backend (SQLite + dev auth out of the box)
cd staccato-backend && uv venv --python 3.12 && source .venv/bin/activate
uv pip install -e '.[dev]' && pytest -m "not slow" && uvicorn staccato_backend.main:app

# Public web + admin
cd staccato-frontend && npm install && npm run dev        # :3000
cd staccato-admin && npm install && npm run dev           # :3100

# iOS: see https://github.com/shawnwelch/staccato-apple (XcodeGen; PacingKit tests run with `swift test`)
```

## Build order / status

1. ✅ Backend: engine + `POST /v1/analyses` + worker + dedupe (the MVP core)
2. ✅ Frontend: share pages + leaderboard
3. ✅ Channel classification jobs + admin launcher (seed the leaderboard next)
4. ✅ iOS Scan/Browse/Settings + StoreKit + free-tier gating (needs Xcode-side wiring)
5. 🚧 Live capture: pipeline scaffolding in place, feature-flagged off; CV
   hardening (moiré/glare/keystone) + TestFlight validation before the paid claim ships
