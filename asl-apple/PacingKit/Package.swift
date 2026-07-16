// swift-tools-version: 6.0
// PacingKit — the ASL scoring engine, ported from the Python reference in
// asl-backend/asl_backend/engine/scoring.py. Pure Swift, no platform
// dependencies: `swift test` runs on macOS and Linux as well as inside Xcode.

import PackageDescription

let package = Package(
    name: "PacingKit",
    // Modest floors on purpose: the engine is pure math and should stay
    // testable everywhere. The app target pins its own iOS 26 deployment.
    platforms: [
        .iOS(.v17),
        .macOS(.v14),
    ],
    products: [
        .library(name: "PacingKit", targets: ["PacingKit"])
    ],
    targets: [
        .target(
            name: "PacingKit"
        ),
        .testTarget(
            name: "PacingKitTests",
            dependencies: ["PacingKit"],
            resources: [
                // Copied verbatim from <repo root>/fixtures/golden_vectors.json.
                // Keep in sync: the backend's pytest suite and this test target
                // must both pass the same file at the same engine version.
                .copy("Fixtures")
            ]
        ),
    ]
)
