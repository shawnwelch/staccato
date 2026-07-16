# asl-apple

iOS app for ASL — the video pacing scorer. ASL measures how fast a video
changes shots and reports a 0–100 pacing intensity score plus a heat map of
cut density.

Copy rule for every surface in this app: **describe what is measured, never
effects on anyone.** Labels are `calm` / `moderate` / `fast` / `hyper-paced`
— never good/bad/safe/harmful.

## Layout

```
asl-apple/
  project.yml          XcodeGen spec (app, share extension, unit tests)
  PacingKit/           SPM package: the scoring engine (pure Swift, no UIKit)
    Sources/PacingKit/PacingEngine.swift
    Tests/PacingKitTests/GoldenVectorTests.swift
    Tests/PacingKitTests/Fixtures/golden_vectors.json
  ASL/                 App sources (SwiftUI, Swift 6 strict concurrency, iOS 26)
    App/               Entry point, tab root, cross-tab router
    Scan/              URL scan flow: submit → poll → score reveal → share
    Live/              On-device optical capture (feature-flagged, paid)
    Browse/            Leaderboard + channel pages (always free)
    Settings/          Account, subscription, engine version, methodology
    Networking/        APIClient actor + wire models
    Auth/              ClerkSession (SDK drop-in points marked TODO(clerk))
    Purchases/         SubscriptionManager (StoreKit 2, "asl.monthly.999")
    Support/           AppConfig, FeatureFlags, Theme, app-group handoff
  ASLTests/            App-layer unit tests
  ShareExtension/      "Scan with ASL" share-sheet extension
```

## Building

Requires Xcode with the iOS 26 SDK and [XcodeGen](https://github.com/yonaskolb/XcodeGen):

```sh
brew install xcodegen
cd asl-apple
xcodegen generate     # writes ASL.xcodeproj from project.yml
open ASL.xcodeproj
```

`ASL.xcodeproj` is generated output — don't hand-edit it or commit it; change
`project.yml` and regenerate.

### Running PacingKit tests without Xcode

PacingKit is a pure SwiftPM package (no UIKit/AVFoundation), so the engine
test suite runs anywhere Swift runs, including Linux CI:

```sh
cd asl-apple/PacingKit
swift test
```

## The engine-parity contract (read this before touching PacingEngine.swift)

`PacingKit/Sources/PacingKit/PacingEngine.swift` is a port of
`asl-backend/asl_backend/engine/scoring.py` and must match it **bit-for-bit**
at the same engine version (currently `1.0.0`). The contract is pinned by
shared golden vectors:

- source of truth: `<repo root>/fixtures/golden_vectors.json`
- Swift copy: `PacingKit/Tests/PacingKitTests/Fixtures/golden_vectors.json`
  (copied verbatim; keep in sync whenever the fixture changes)

The backend's pytest suite and `GoldenVectorTests` must both pass the same
fixture at the same version. Any change to the scoring constants, the median
basis, the heat-map windowing, or thresholds is a **new engine version** on
both sides simultaneously — stored scores carry their engine version and are
never silently rescored.

Score math, for orientation: `score = 100 / (1 + (median_shot_s / 11) ^ 1.3)`,
labels at <25 calm, <50 moderate, <75 fast, else hyper-paced.

## Architecture notes

- **PacingKit vs app**: everything that computes a score lives in the
  package; the app only formats and transports numbers. Live capture calls
  `PacingEngine.summarize` at session end so the on-device score equals what
  the server recomputes from the submitted cut times (the server never trusts
  client math for published data).
- **APIClient** is an actor; base URL comes from Info.plist
  (`ASLAPIBaseURL`, injected via project.yml). Typed errors include
  `.quotaExhausted(remaining:)` for 402 — quota exhaustion routes to the
  paywall, never to an error state, and the Browse tab is always reachable.
  The free-scan count shown in Scan is exclusively server-reported
  (`X-Scans-Remaining` header or response body) — the client never estimates.
- **Live pipeline** (`ASL/Live/`) is five protocol-separated stages: camera →
  quad detection (Vision) → temporal stabilization → perspective
  rectification (Core Image) → adaptive frame differencing. Frame processing
  is confined to the `LiveCaptureEngine` actor; only cut timestamps ever
  leave it. Known-hostile CV conditions (moiré, glare, keystone, PWM banding)
  are marked with `TODO(cv)` at the exact spots the mitigations belong.
- **Share extension** drops the shared URL into the app-group defaults
  (`group.com.staccato.asl`); the app consumes it on next foreground.
  The `asl://scan?url=` deep link exists for surfaces that may open the app.
- **Feature flags**: `FeatureFlags.liveCaptureEnabled` defaults to false; the
  Live tab does not exist until it flips, and is additionally
  subscription-gated.

## Xcode-side setup still required

These can't be represented (or verified) in this repo and get wired in Xcode
/ App Store Connect / the Clerk dashboard:

1. **Signing**: team + real bundle identifiers (placeholders are
   `com.staccato.asl` / `com.staccato.asl.share`).
2. **App group**: register `group.com.staccato.asl` (or your real id) and
   update `AppGroup.identifier`, `ShareViewController.appGroupID`, and both
   entitlements blocks in `project.yml` — all four must match.
3. **Clerk iOS SDK**: add the package dependency and fill in the
   `TODO(clerk)` bodies in `ASL/Auth/ClerkSession.swift` (configure the
   publishable key, sign-in UI, and session-token fetch). Nothing else in the
   app touches Clerk types.
4. **StoreKit**: create the `asl.monthly.999` auto-renewable subscription in
   App Store Connect; add a StoreKit configuration file to the scheme for
   local testing.
5. **Environment config**: set `ASLAPIBaseURL` / `ASLFrontendHost` in
   `project.yml` to the real hosts.
6. **Camera permission** is already declared (`NSCameraUsageDescription`);
   review the copy stays accurate if capture behavior changes.
