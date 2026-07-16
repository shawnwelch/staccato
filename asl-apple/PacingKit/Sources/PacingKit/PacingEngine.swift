// PacingEngine.swift
// PacingKit
//
// Pure scoring math: pacing score + heat map.
//
// This is a line-for-line port of asl-backend/asl_backend/engine/scoring.py
// and MUST match it bit-for-bit at the same `engineVersion`. Both sides are
// pinned by the shared golden vectors in fixtures/golden_vectors.json (copied
// into this package's test bundle). Nothing here touches video frames or the
// network — inputs are cut timestamps and durations, outputs are numbers.
//
// Any change to the constants below (or to the median basis) is a new engine
// version: every stored score carries the engine version and is never
// silently rescored.

import Foundation

/// Neutral pacing label. Order matters: thresholds ascend.
///
/// Labels describe measured pacing only ("calm" ... "hyper-paced"); they are
/// never value judgments (good/bad/safe/harmful) and UI copy must not imply
/// effects on viewers.
public enum PacingLabel: String, Sendable, Codable, Hashable, CaseIterable {
    case calm
    case moderate
    case fast
    case hyperPaced = "hyper-paced"
}

/// Everything a surface needs to display a result.
///
/// Mirrors `CutSummary` in the backend (`scoring.py`); field-for-field parity
/// is asserted by the golden-vector tests.
public struct CutSummary: Sendable, Equatable {
    public let engineVersion: String
    public let durationS: Double
    public let cutCount: Int
    public let medianShotS: Double
    public let cutsPerMinute: Double
    public let score: Double
    public let label: PacingLabel
    public let heatmapBinCentersS: [Double]
    public let heatmapCutsPerMin: [Double]

    public init(
        engineVersion: String,
        durationS: Double,
        cutCount: Int,
        medianShotS: Double,
        cutsPerMinute: Double,
        score: Double,
        label: PacingLabel,
        heatmapBinCentersS: [Double],
        heatmapCutsPerMin: [Double]
    ) {
        self.engineVersion = engineVersion
        self.durationS = durationS
        self.cutCount = cutCount
        self.medianShotS = medianShotS
        self.cutsPerMinute = cutsPerMinute
        self.score = score
        self.label = label
        self.heatmapBinCentersS = heatmapBinCentersS
        self.heatmapCutsPerMin = heatmapCutsPerMin
    }
}

/// The scoring engine. Stateless; all members are pure functions of their
/// inputs, so the whole namespace is trivially Sendable.
public enum PacingEngine {

    /// Must equal `ENGINE_VERSION` in asl-backend/asl_backend/engine/scoring.py.
    public static let engineVersion = "1.0.0"

    /// Median shot length (seconds) that maps to score 50.
    static let pivotSeconds = 11.0
    /// Logistic exponent.
    static let steepness = 1.3

    public static let defaultBinS = 2.0
    public static let defaultWindowS = 10.0

    // MARK: - Score

    /// 0–100 pacing intensity from the MEDIAN shot length.
    ///
    /// Logistic in log-space of shot length: `score = 100 / (1 + (m / 11) ^ 1.3)`.
    /// Anchors: 34s → ~19 (calm), 11s → 50, 3s → ~84, 1.5s → ~93 (hyper-paced).
    /// Median (not mean) so long intros/credits don't skew the result.
    public static func pacingScore(medianShotLength m: Double) -> Double {
        precondition(m > 0, "median shot length must be positive")
        return 100.0 / (1.0 + pow(m / pivotSeconds, steepness))
    }

    /// Neutral pacing label. <25 calm, <50 moderate, <75 fast, else hyper-paced.
    public static func label(forScore score: Double) -> PacingLabel {
        if score < 25.0 { return .calm }
        if score < 50.0 { return .moderate }
        if score < 75.0 { return .fast }
        return .hyperPaced
    }

    // MARK: - Shots

    /// Shot lengths implied by cut timestamps within [0, duration].
    ///
    /// Cuts are boundaries; a video with k cuts has k+1 shots (first shot
    /// starts at 0, last shot ends at duration). Zero-length shots (duplicate
    /// cut timestamps) are dropped.
    public static func shotLengths(cutTimes: [Double], duration: Double) -> [Double] {
        precondition(duration > 0, "duration must be positive")
        var boundaries: [Double] = [0.0]
        boundaries.append(contentsOf: cutTimes.filter { $0 > 0.0 && $0 < duration }.sorted())
        boundaries.append(duration)

        var lengths: [Double] = []
        lengths.reserveCapacity(boundaries.count - 1)
        for i in 1..<boundaries.count {
            let d = boundaries[i] - boundaries[i - 1]
            if d > 0.0 {
                lengths.append(d)
            }
        }
        return lengths
    }

    /// Median with Python `statistics.median` semantics: sort; odd count →
    /// middle element; even count → arithmetic mean of the two middle
    /// elements.
    public static func median(_ values: [Double]) -> Double {
        precondition(!values.isEmpty, "median of empty array is undefined")
        let sorted = values.sorted()
        let n = sorted.count
        if n % 2 == 1 {
            return sorted[n / 2]
        }
        return (sorted[n / 2 - 1] + sorted[n / 2]) / 2.0
    }

    // MARK: - Heat map

    /// Rolling cut density over the timeline, normalized to cuts/min.
    ///
    /// The timeline is split into bins of `binS`. For each bin center t, count
    /// the cuts inside the centered window [t - windowS/2, t + windowS/2)
    /// clipped to [0, duration], and normalize by the CLIPPED window length so
    /// edge bins aren't artificially deflated.
    ///
    /// Returns (binCenters, cutsPerMin), both `count == ceil(duration / binS)`.
    public static func buildHeatmap(
        cutTimes: [Double],
        duration: Double,
        binS: Double = defaultBinS,
        windowS: Double = defaultWindowS
    ) -> (binCenters: [Double], cutsPerMin: [Double]) {
        precondition(duration > 0, "duration must be positive")
        precondition(binS > 0 && windowS > 0, "binS and windowS must be positive")

        let cuts = cutTimes.filter { $0 >= 0.0 && $0 <= duration }.sorted()
        let nBins = max(1, Int((duration / binS).rounded(.up)))
        let half = windowS / 2.0

        var centers: [Double] = []
        var densities: [Double] = []
        centers.reserveCapacity(nBins)
        densities.reserveCapacity(nBins)

        for i in 0..<nBins {
            let center = (Double(i) + 0.5) * binS
            let lo = max(0.0, center - half)
            let hi = min(duration, center + half)
            var count = 0
            for t in cuts where t >= lo && t < hi {
                count += 1
            }
            let span = hi - lo
            centers.append(center)
            // Order of operations matches the reference: (count / span) * 60.
            densities.append(span > 0 ? (Double(count) / span) * 60.0 : 0.0)
        }
        return (centers, densities)
    }

    // MARK: - Full pipeline

    /// Full scoring pipeline from cut timestamps (the shared entry point).
    ///
    /// Used for the live-capture end-of-session score. The backend recomputes
    /// the same summary from the submitted cut times, so device math is never
    /// trusted for published data — this exists so the on-device number equals
    /// the server's number.
    public static func summarize(
        cutTimes: [Double],
        duration: Double,
        binS: Double = defaultBinS,
        windowS: Double = defaultWindowS
    ) -> CutSummary {
        let lengths = shotLengths(cutTimes: cutTimes, duration: duration)
        let medianShot = median(lengths)
        let score = pacingScore(medianShotLength: medianShot)
        let heatmap = buildHeatmap(cutTimes: cutTimes, duration: duration, binS: binS, windowS: windowS)
        let inRange = cutTimes.filter { $0 > 0.0 && $0 < duration }.count
        return CutSummary(
            engineVersion: engineVersion,
            durationS: duration,
            cutCount: inRange,
            medianShotS: medianShot,
            cutsPerMinute: Double(inRange) / (duration / 60.0),
            score: score,
            label: label(forScore: score),
            heatmapBinCentersS: heatmap.binCenters,
            heatmapCutsPerMin: heatmap.cutsPerMin
        )
    }
}
