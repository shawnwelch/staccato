# asl-backend

API + workers for the ASL pacing scorer. Python 3.12, FastAPI, SQLAlchemy 2
(async), Procrastinate (Postgres-backed job queue), PySceneDetect.

## Layout

```
asl_backend/
  engine/          the scoring engine (open-core: no imports from app code;
                   extraction into a standalone OSS repo is file-copy trivial)
  api/             FastAPI routers (analyses, live-sessions, public, apple, admin)
  jobs/            Procrastinate app + tasks (analyze_url, classify_channel, finalizer)
  providers/       video provider interface; YouTube first
  deps/            entitlements — the ONE place gating lives
tests/             golden vectors, synthetic-clip e2e, entitlement races, inline jobs
```

## The engine contract

- Score = `100 / (1 + (median_shot_s / 11.0) ** 1.3)`, labels <25 calm,
  <50 moderate, <75 fast, else hyper-paced. **Median**, not mean.
- Every stored score carries `engine_version` (currently `1.0.0`). Changing
  `_PIVOT_SECONDS`, `_STEEPNESS`, or the median basis is a version bump and a
  deliberate re-score rollout (see `/admin/rescore`), never a silent change.
- `../fixtures/golden_vectors.json` pins the math; the Swift port in
  [staccato-apple](https://github.com/shawnwelch/staccato-apple) runs the
  same vectors from byte-identical copies. Regenerate only on a version bump,
  and copy the regenerated file into staccato-apple in the same change.

## Run it

```bash
uv venv --python 3.12 && source .venv/bin/activate
uv pip install -e '.[dev]'

# API
uvicorn asl_backend.main:app --reload
# Worker (needs Postgres; procrastinate schema: `procrastinate schema --apply`)
procrastinate --app=asl_backend.jobs.app worker
# Cron entry (channel re-scans)
python -m asl_backend.cron
```

Defaults run on SQLite + local media storage with `ASL_AUTH_MODE=dev`
(`Authorization: Bearer dev:<user-id>`), so the whole stack works with zero
external accounts. See `.env.example` for the production knobs (Neon,
Clerk JWKS, Cloudflare R2, YouTube Data API key).

## Tests

```bash
pytest -m "not slow"      # fast: engine golden vectors, API, entitlements
pytest                    # + synthetic-clip detection e2e (renders real videos)
ASL_TEST_PG_DSN=postgresql+asyncpg://... pytest tests/test_entitlements_concurrency.py
```

The Postgres DSN enables the real row-lock race test (two concurrent submits
must never both take the last free credit).

## Deploy (Render)

Three services off this repo (see root `render.yaml`):
- **web**: `uvicorn asl_backend.main:app`
- **worker**: `procrastinate --app=asl_backend.jobs.app worker`
- **cron**: `python -m asl_backend.cron` on a schedule

Neon Postgres and Cloudflare R2 (S3-compatible; chosen for zero egress fees)
are external. Queues: `interactive` (user watching a spinner) and `batch`
(channel fan-outs; throttle via `ASL_BATCH_QUEUE_THROTTLE_S`).

## Notes

- Dedupe: a repeated URL at the same engine version returns the cached result
  instantly and never burns a free credit.
- Optical (live-capture) scores are recomputed server-side from submitted cut
  times and stay out of canonical pools until promoted in asl-admin.
- Job enqueue happens after the analysis row commits; a failed enqueue marks
  the row `failed` immediately, and `/admin/jobs/{id}/retry` re-runs failures.
