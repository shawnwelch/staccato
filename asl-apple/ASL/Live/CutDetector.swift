// CutDetector.swift
// ASL
//
// Frame differencing with an adaptive threshold. Pipeline per rectified frame:
//
//   1. downscale to a tiny luma-ish thumbnail (kills sensor noise + moiré)
//   2. mean absolute difference vs the previous thumbnail (CIDifferenceBlend
//      + CIAreaAverage → one scalar)
//   3. compare against rolling statistics: a cut is a difference spike well
//      above the recent baseline, not an absolute level — so it self-tunes
//      to bright/dim rooms and high/low-motion content
//   4. refractory period so one cut isn't double-counted across 2-3 frames
//
// The scalar per frame is the ONLY thing kept; frames are never stored.

import CoreImage
import CoreImage.CIFilterBuiltins
import Foundation

struct AdaptiveCutDetector: CutDetecting {

    // MARK: Tuning

    /// Thumbnail width in pixels. Small enough to smooth away moiré and
    /// compression shimmer, large enough that a real shot change moves the
    /// average a lot.
    private let thumbnailWidth: CGFloat = 32
    /// Spike threshold: diff > mean + k·stddev of the recent window.
    private let sigmaMultiplier = 3.5
    /// Absolute floor so a perfectly static screen (stddev → 0) doesn't turn
    /// sensor noise into "cuts". Units: mean-abs-difference in [0, 1].
    private let minimumSpike = 0.04
    /// Ignore new cuts for this long after one fires (a hard cut bleeds
    /// across 2-3 frames of a 30fps capture).
    private let refractorySeconds: TimeInterval = 0.3
    /// Need this many baseline samples before we trust the statistics.
    private let warmupSamples = 15
    /// Rolling-statistics window (~4s at 30fps).
    private let windowSize = 120

    // MARK: State

    private let context = CIContext(options: [.cacheIntermediates: false])
    private var previousThumbnail: CIImage?
    private var recentDiffs: [Double] = []
    private var lastCutTime: TimeInterval = -.infinity

    // MARK: CutDetecting

    mutating func process(_ rectified: CIImage, at timestamp: TimeInterval) -> Bool {
        guard let thumbnail = downscale(rectified) else { return false }
        defer { previousThumbnail = thumbnail }

        guard let previous = previousThumbnail,
              let diff = meanAbsoluteDifference(thumbnail, previous)
        else { return false }

        // TODO(cv): glare — a lamp reflection sweeping the screen as the
        // viewer's hand moves produces a smooth diff ramp, not a spike.
        // The sigma test rejects most of it, but a slow bright sweep can
        // still crest the threshold; a highlight mask (clip pixels near 1.0
        // before differencing) is the likely fix.
        //
        // TODO(cv): PWM/refresh banding — rolling bands add a periodic
        // component to the diff signal. If observed in the field, notch it:
        // track diff autocorrelation and subtract the periodic baseline.
        //
        // TODO(cv): gradual transitions (dissolves/fades) spread their energy
        // over many frames and will read as "no cut". Engine 1.x measures
        // hard cuts only; this is a documented measurement boundary, not a
        // bug — parity with the server-side detector matters more than
        // catching every dissolve.

        let isWarm = recentDiffs.count >= warmupSamples
        let (mean, stddev) = runningStats()
        let threshold = max(mean + sigmaMultiplier * stddev, minimumSpike)
        let refractoryOver = timestamp - lastCutTime >= refractorySeconds

        var isCut = false
        if isWarm && refractoryOver && diff > threshold {
            isCut = true
            lastCutTime = timestamp
            // Do NOT feed the spike itself into the baseline — that would
            // raise the threshold right after every cut and mask rapid
            // sequences, exactly the content this app exists to measure.
        } else {
            recentDiffs.append(diff)
            if recentDiffs.count > windowSize {
                recentDiffs.removeFirst()
            }
        }
        return isCut
    }

    mutating func reset() {
        previousThumbnail = nil
        recentDiffs.removeAll()
        lastCutTime = -.infinity
    }

    // MARK: Internals

    private func downscale(_ image: CIImage) -> CIImage? {
        let extent = image.extent
        guard extent.width > 0, extent.height > 0 else { return nil }
        let scale = thumbnailWidth / extent.width

        let filter = CIFilter.lanczosScaleTransform()
        filter.inputImage = image
        filter.scale = Float(scale)
        filter.aspectRatio = 1.0
        guard let output = filter.outputImage else { return nil }
        // Rasterize now so the diff below compares settled pixels, and so
        // the (tiny) render happens once per frame, not once per use.
        guard let rendered = context.createCGImage(output, from: output.extent) else { return nil }
        return CIImage(cgImage: rendered)
    }

    /// Mean absolute per-pixel difference across the two thumbnails,
    /// averaged over RGB, in [0, 1].
    private func meanAbsoluteDifference(_ a: CIImage, _ b: CIImage) -> Double? {
        let diffFilter = CIFilter.differenceBlendMode()
        diffFilter.inputImage = a
        diffFilter.backgroundImage = b
        guard let diffImage = diffFilter.outputImage else { return nil }

        let clamped = diffImage.cropped(to: a.extent.intersection(b.extent))
        guard !clamped.extent.isEmpty else { return nil }

        let averageFilter = CIFilter.areaAverage()
        averageFilter.inputImage = clamped
        averageFilter.extent = clamped.extent
        guard let averaged = averageFilter.outputImage else { return nil }

        // Render the 1x1 average pixel and read it back.
        var pixel = [UInt8](repeating: 0, count: 4)
        context.render(
            averaged,
            toBitmap: &pixel,
            rowBytes: 4,
            bounds: CGRect(x: 0, y: 0, width: 1, height: 1),
            format: .RGBA8,
            colorSpace: CGColorSpaceCreateDeviceRGB()
        )
        let r = Double(pixel[0]) / 255.0
        let g = Double(pixel[1]) / 255.0
        let bch = Double(pixel[2]) / 255.0
        return (r + g + bch) / 3.0
    }

    private func runningStats() -> (mean: Double, stddev: Double) {
        guard !recentDiffs.isEmpty else { return (0, 0) }
        let mean = recentDiffs.reduce(0, +) / Double(recentDiffs.count)
        let variance = recentDiffs.reduce(0) { $0 + ($1 - mean) * ($1 - mean) }
            / Double(recentDiffs.count)
        return (mean, variance.squareRoot())
    }
}
