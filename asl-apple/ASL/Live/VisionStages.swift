// VisionStages.swift
// ASL
//
// Screen-quad detection (Vision) + temporal stabilization + perspective
// rectification (Core Image). These stages turn "a phone pointed at a TV"
// into a stable, flat image of just the TV picture, so the cut detector
// downstream sees content changes rather than camera shake or room light.
//
// Known-hostile conditions this pipeline must eventually survive (tracked as
// TODOs at the relevant spots below):
//   - moiré between the display's pixel grid and the camera sensor
//   - specular glare / reflections moving across the screen
//   - strong keystone (viewing the screen at a sharp angle)
//   - PWM/refresh banding (rolling bands from display refresh vs shutter)

import CoreImage
import CoreImage.CIFilterBuiltins
import Foundation
import Vision

// MARK: - Detection

/// VNDetectRectanglesRequest tuned for TVs/monitors/tablets.
struct VisionScreenQuadDetector: ScreenQuadDetecting {

    private let minimumConfidence: VNConfidence = 0.6

    func detectQuad(in frame: CapturedFrame) throws -> ScreenQuad? {
        let request = VNDetectRectanglesRequest()
        // Screens span roughly 9:16 (portrait tablet) to 21:9. Vision's
        // aspect ratio is min/max side, so accept a broad band.
        request.minimumAspectRatio = 0.3
        request.maximumAspectRatio = 1.0
        // Ignore tiny candidates (picture frames, windows across the room).
        request.minimumSize = 0.15
        // Tolerate some keystone; heavy keystone correction quality is a
        // TODO below in the rectifier.
        request.quadratureTolerance = 20
        request.minimumConfidence = minimumConfidence
        request.maximumObservations = 3

        let handler = VNImageRequestHandler(cvPixelBuffer: frame.pixelBuffer, options: [:])
        try handler.perform([request])

        // Prefer the largest confident quad: when a TV and its reflection (or
        // a poster) both match, the screen is almost always the biggest.
        let best = (request.results ?? [])
            .filter { $0.confidence >= minimumConfidence }
            .max { area(of: $0) < area(of: $1) }

        guard let best else { return nil }
        return ScreenQuad(
            topLeft: best.topLeft,
            topRight: best.topRight,
            bottomRight: best.bottomRight,
            bottomLeft: best.bottomLeft
        )
    }

    private func area(of observation: VNRectangleObservation) -> CGFloat {
        // Shoelace formula over the quad corners (normalized coords).
        let p = [observation.topLeft, observation.topRight,
                 observation.bottomRight, observation.bottomLeft]
        var sum: CGFloat = 0
        for i in 0..<4 {
            let a = p[i], b = p[(i + 1) % 4]
            sum += a.x * b.y - b.x * a.y
        }
        return abs(sum) / 2
    }
}

// MARK: - Stabilization

/// Exponential-moving-average smoothing of quad corners plus short dropout
/// tolerance. Rationale: raw per-frame detections jitter by a few pixels;
/// unsmoothed, that jitter shifts the rectified image every frame and the
/// differencer reads it as motion.
struct EMAQuadStabilizer: QuadStabilizing {

    /// Blend weight for new observations (higher = snappier, noisier).
    private let alpha: CGFloat = 0.25
    /// Keep using the last good quad for this long after detection drops out
    /// (momentary occlusion, autofocus hunting).
    private let dropoutTolerance: TimeInterval = 0.5
    /// A new detection whose corners jump farther than this (normalized) from
    /// the smoothed quad is treated as a re-acquire, not smoothed into it.
    private let reacquireDistance: CGFloat = 0.15

    private var smoothed: ScreenQuad?
    private var lastDetectionTime: TimeInterval?

    mutating func stabilize(_ raw: ScreenQuad?, at timestamp: TimeInterval) -> ScreenQuad? {
        if let raw {
            lastDetectionTime = timestamp
            if let current = smoothed {
                if maxCornerDistance(current, raw) > reacquireDistance {
                    // The quad moved a lot — camera re-aimed or a different
                    // screen; snap instead of gliding across the room.
                    smoothed = raw
                } else {
                    smoothed = current.mixed(with: raw, weight: alpha)
                }
            } else {
                smoothed = raw
            }
            return smoothed
        }

        // Dropout: coast on the last quad briefly, then declare loss.
        if let lastTime = lastDetectionTime, timestamp - lastTime <= dropoutTolerance {
            return smoothed
        }
        smoothed = nil
        return nil
    }

    mutating func reset() {
        smoothed = nil
        lastDetectionTime = nil
    }

    private func maxCornerDistance(_ a: ScreenQuad, _ b: ScreenQuad) -> CGFloat {
        func d(_ p: CGPoint, _ q: CGPoint) -> CGFloat {
            hypot(p.x - q.x, p.y - q.y)
        }
        return max(
            d(a.topLeft, b.topLeft), d(a.topRight, b.topRight),
            d(a.bottomRight, b.bottomRight), d(a.bottomLeft, b.bottomLeft)
        )
    }
}

// MARK: - Rectification

/// CIPerspectiveCorrection: maps the detected quad to an axis-aligned image.
struct PerspectiveRectifier: FrameRectifying {

    func rectify(_ frame: CapturedFrame, quad: ScreenQuad) -> CIImage? {
        let image = CIImage(cvPixelBuffer: frame.pixelBuffer)
        let extent = image.extent

        // Vision coords are normalized, origin bottom-left — same origin as
        // Core Image, so scaling by the extent is the whole conversion.
        func point(_ p: CGPoint) -> CGPoint {
            CGPoint(x: extent.origin.x + p.x * extent.width,
                    y: extent.origin.y + p.y * extent.height)
        }

        let filter = CIFilter.perspectiveCorrection()
        filter.inputImage = image
        filter.topLeft = point(quad.topLeft)
        filter.topRight = point(quad.topRight)
        filter.bottomRight = point(quad.bottomRight)
        filter.bottomLeft = point(quad.bottomLeft)

        // TODO(cv): heavy keystone — at sharp viewing angles the far edge of
        // the screen is heavily minified; after correction that edge is
        // effectively upsampled and noisy, which inflates frame-difference
        // energy. Consider weighting the differencer by local sampling
        // density, or refusing to score below a minimum quad "rectangularity".

        // TODO(cv): moiré — the display pixel grid can alias against the
        // sensor. The downscale in AdaptiveCutDetector suppresses most of it;
        // if it still leaks through, add a slight gaussian pre-blur here
        // (radius ~1-2px at capture resolution) before correction.

        return filter.outputImage
    }
}
