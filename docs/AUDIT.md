# Security & Efficiency Audit

("Staccato Score" is the product's video pacing rating — this document
deliberately doesn't use the name.)

A codebase health audit in the product's own spirit: a neutral instrument
that reports what it measures, on a 0–100 scale. The overall number is a
weighted average of seven categories, each scored against the checklist
below. Re-audit after any security-relevant change — and like the engine
itself, never silently: record the date and commit.

## Scorecard

**Audit date:** 2026-07-18 · **Commit base:** `97138fa` · **Methodology version:** 1.0.0

| Category | Weight | Before | After | Notes |
|---|---|---|---|---|
| Authentication & access control | 25% | 38 | 82 | admin panel was un-gated; now fail-closed everywhere |
| Payments & entitlement integrity | 15% | 55 | 90 | Apple chain pinning was already strong; scope checks added |
| Input handling & abuse resistance | 15% | 62 | 80 | DoS bounds added; rate limiting still open |
| Data exposure & transport | 10% | 70 | 85 | CORS narrowed, security headers added |
| Supply chain & configuration | 10% | 60 | 65 | needs dependency audit + migrations (open) |
| Efficiency — hot request paths | 15% | 55 | 88 | leaderboard, heat map, JWKS all rewritten |
| Efficiency — jobs & data layer | 10% | 60 | 82 | N+1s removed, composite indexes added |
| **Overall (weighted)** | | **54** | **82** | |

## What the audit found (and what was fixed)

### Critical

1. **The admin app had no authentication.** `staccato-admin/middleware.ts`
   passed every request through — even in production, even with Clerk keys
   set — while its server routes attach `ADMIN_API_TOKEN` to every backend
   call. A deployed admin URL was a fully open admin panel (moderation,
   job control, rescoring). **Fixed:** production now refuses to serve until
   Clerk gating is wired in (`503`, break-glass env override available).
   Wiring real Clerk org-gating remains a launch blocker (see roadmap).
2. **Apple IAP notifications weren't scoped to the app.** Chain validation
   to pinned Apple roots was already rigorous — but Apple signs Server
   Notifications for *every* app with that same chain, and `bundleId` /
   `environment` were never checked (`STACCATO_APPLE_BUNDLE_ID` existed and
   was used nowhere). Any developer's legitimately-signed notification —
   with an `appAccountToken` they control — could mint a pro entitlement
   for an arbitrary user; Sandbox purchases would also have counted in
   prod. **Fixed:** bundle id required to match, Sandbox rejected in prod.

### High

3. **Prod misconfiguration failed open, not closed.** `auth_mode=dev` in a
   prod deploy would have accepted `Bearer dev:<anyone>`; a missing
   `STACCATO_ADMIN_API_TOKEN` left the literal default `dev-admin-token`
   accepted. **Fixed:** both are refused when `STACCATO_ENV=prod`.
4. **Admin token compared with `!=`.** Timing-unsafe comparison on the one
   static credential in the system. **Fixed:** `hmac.compare_digest`.
5. **Live-capture input was a DoS vector.** `duration_s` had no upper bound
   and heat-map size scales with duration: a pro user posting
   `duration_s=1e12` would OOM the API worker. Floats also admitted
   NaN/inf. **Fixed:** duration ceiling (configurable, default 6h),
   `allow_inf_nan=False`, `device_score` bounded to 0–100.

### Medium

6. **CORS was `*` for every route** including `/admin` and all write
   endpoints. **Fixed:** configurable allowlist
   (`STACCATO_CORS_ALLOW_ORIGINS`), methods/headers narrowed; dev default
   unchanged.
7. **JWKS handling broke on key rotation** (unknown `kid` → all requests
   401 for up to an hour) and cold caches stampeded the JWKS endpoint.
   **Fixed:** single-flight fetch + rate-limited forced refresh on unknown
   `kid`.
8. **First-sight user mirroring raced.** Two concurrent first requests from
   a new user could `IntegrityError`. **Fixed:** `INSERT … ON CONFLICT DO
   NOTHING`.
9. **No security headers on either Next.js app.** **Fixed:** frame,
   content-type-sniffing, and referrer policies on both; admin additionally
   `noindex`.

### Efficiency

10. **Leaderboard loaded every channel into Python** and sorted/paginated
    in memory per request. **Fixed:** `ORDER BY … LIMIT/OFFSET` in SQL with
    deterministic tie-breaking.
11. **`build_heatmap` was O(bins × cuts).** A 2-hour video with dense cuts
    paid ~3600 bins × thousands of cuts per render. **Fixed:** binary
    search over the sorted cut list — verified bit-identical against the
    golden vectors (no `ENGINE_VERSION` bump needed).
12. **Admin `/rescore` ran one query per video plus one commit per row.**
    **Fixed:** one set-based `NOT EXISTS` query, one commit.
13. **`finalize_channel_score` ran two queries per video.** **Fixed:** two
    queries per batch.
14. **Missing composite indexes** for the dedupe path
    (`analyses(video_id, status, engine_version)`) and the leaderboard's
    latest-score lookup (`channel_scores(channel_id, computed_at)`).
    **Fixed** in the models (apply via migration in prod — see roadmap).

### Already strong (kept, and worth keeping)

- URL normalization allowlists YouTube video ids before anything touches
  the network — no SSRF surface through `yt-dlp`.
- Free-tier gating is server-side behind `SELECT … FOR UPDATE`, with a
  dedicated Postgres race test in CI.
- Client math is never trusted: live-session scores are recomputed
  server-side; optical scans are quarantined until moderated.
- In-flight/failed analyses 404 (not 403) for non-owners, so ids don't leak.
- Apple x5c chain validation pins to on-disk Apple roots and fails closed.
- `ADMIN_API_TOKEN` is `generateValue: true` in `render.yaml` and never
  reaches a client bundle.

## What's still missing (the honest part of the score)

Ranked; the first two gate a public launch.

1. **Wire Clerk org-gating into staccato-admin for real** (the middleware
   now fails closed in prod, but that blocks the tool — the TODO(clerk)
   drop-in is the actual fix).
2. **Database migrations.** Prod schema is "managed by migrations" that
   don't exist in the repo; the new indexes and any future column need
   Alembic (or equivalent) before the next schema change.
3. **Rate limiting.** Nothing throttles `POST /v1/analyses` (each call can
   trigger a yt-dlp download) or the public read endpoints; the share-page
   view counter writes to the DB on every uncached hit.
4. **Dependency auditing in CI** (`pip-audit` / `npm audit`) and a pinned
   backend lockfile (`uv lock`); yt-dlp especially needs a fast update
   cadence.
5. **JWT audience/authorized-party check** — `verify_aud` is off (normal
   for Clerk, which uses `azp`), so tokens minted for another Clerk app in
   the same tenant would verify. Verify `azp` against an allowlist.
6. **Observability:** no structured request logging, error tracker, or
   worker metrics; the ops story today is the admin jobs page.
7. **Object-storage hygiene:** R2 keys are predictable
   (`analyses/{id}/…`) — fine for public results, but revisit if private
   artifacts ever land.
