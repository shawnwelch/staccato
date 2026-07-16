// CapturePipeline.swift
// ASL
//
// The on-device optical cut detector, decomposed into five swappable stages:
//
//   camera (30fps) → screen-quad detection → temporal stabilization
//                  → perspective rectification → frame differencing → cuts
//
// PRIVACY INVARIANT: no stage retains frames beyond the previous/current
// pair, and nothing in this pipeline touches the network. Only cut
// TIMESTAMPS leave the device (and only when the user taps submit).
//
// Each stage is a protocol so it can be exercised in isolation with synthetic
// frames. The concrete stages live in CameraFrameSource.swift,
// VisionStages.swift, and CutDetector.swift.

import CoreImage
import CoreVideo
import Foundation

// MARK: - Frame plumbing

/// A camera frame crossing from the capture callback into the pipeline actor.
///
/// CVPixelBuffer is not Sendable; this wrapper is safe because the capture
/// output hands us ownership of each buffer and no other code mutates it
/// after capture (`@unchecked Sendable` documents exactly that invariant —
/// do not stash the buffer anywhere that outlives pipeline processing).
struct CapturedFrame: @unchecked Sendable {
    let pixelBuffer: CVPixelBuffer
    /// Seconds since session start (monotonic, from the capture clock).
    let timestamp: TimeInterval
}

/// A screen quadrilateral in Vision's normalized coordinates (origin
/// bottom-left, [0,1] both axes).
struct ScreenQuad: Sendable, Equatable {
    var topLeft: CGPoint
    var topRight: CGPoint
    var bottomRight: CGPoint
    var bottomLeft: CGPoint

    /// Linear blend of two quads (used by the temporal stabilizer's EMA).
    func mixed(with other: ScreenQuad, weight w: CGFloat) -> ScreenQuad {
        func mix(_ a: CGPoint, _ b: CGPoint) -> CGPoint {
            CGPoint(x: a.x + (b.x - a.x) * w, y: a.y + (b.y - a.y) * w)
        }
        return ScreenQuad(
            topLeft: mix(topLeft, other.topLeft),
            topRight: mix(topRight, other.topRight),
            bottomRight: mix(bottomRight, other.bottomRight),
            bottomLeft: mix(bottomLeft, other.bottomLeft)
        )
    }
}

// MARK: - Stage protocols

/// Produces camera frames. The concrete source wraps AVCaptureSession; tests
/// can feed synthetic streams.
protocol FrameSource: Sendable {
    /// Starts capture and returns the frame stream. Throws when the camera
    /// is unavailable or permission is denied.
    func start() async throws -> AsyncStream<CapturedFrame>
    func stop() async
}

/// Finds the TV/monitor/tablet quad in a frame (VNDetectRectanglesRequest in
/// production). Stateless per-frame; returns nil when no plausible screen.
protocol ScreenQuadDetecting {
    func detectQuad(in frame: CapturedFrame) throws -> ScreenQuad?
}

/// Smooths quad jitter across frames and rides out short detection dropouts
/// so the rectified image doesn't swim (which would look like cuts).
protocol QuadStabilizing {
    mutating func stabilize(_ raw: ScreenQuad?, at timestamp: TimeInterval) -> ScreenQuad?
    mutating func reset()
}

/// Rectifies the quad region into a flat, axis-aligned image
/// (CIPerspectiveCorrection in production).
protocol FrameRectifying {
    func rectify(_ frame: CapturedFrame, quad: ScreenQuad) -> CIImage?
}

/// Consumes rectified frames and decides "was that a cut?".
protocol CutDetecting {
    mutating func process(_ rectified: CIImage, at timestamp: TimeInterval) -> Bool
    mutating func reset()
}

// MARK: - Pipeline events

enum LiveCaptureEvent: Sendable {
    /// Screen found / lost (drives the "aim at a screen" UI hint).
    case screenLock(Bool)
    /// A cut was detected at this session-relative timestamp.
    case cutDetected(atTime: TimeInterval)
}

// MARK: - Engine

/// Owns the per-frame loop. An actor so all stage state is confined here,
/// off the main thread, regardless of which queue the camera delivers on.
///
/// Stages are created INSIDE the actor from Sendable factories: the concrete
/// stage types (CIContext, Vision requests, ring buffers) never cross an
/// isolation boundary.
actor LiveCaptureEngine {

    struct StageFactories: Sendable {
        var makeDetector: @Sendable () -> any ScreenQuadDetecting
        var makeStabilizer: @Sendable () -> any QuadStabilizing
        var makeRectifier: @Sendable () -> any FrameRectifying
        var makeCutDetector: @Sendable () -> any CutDetecting

        static let live = StageFactories(
            makeDetector: { VisionScreenQuadDetector() },
            makeStabilizer: { EMAQuadStabilizer() },
            makeRectifier: { PerspectiveRectifier() },
            makeCutDetector: { AdaptiveCutDetector() }
        )
    }

    private var detector: any ScreenQuadDetecting
    private var stabilizer: any QuadStabilizing
    private var rectifier: any FrameRectifying
    private var cutDetector: any CutDetecting

    private(set) var cutTimes: [Double] = []
    private var screenLocked = false

    private let eventContinuation: AsyncStream<LiveCaptureEvent>.Continuation
    /// UI-facing event feed (consumed by LiveSessionController on the main
    /// actor). Single-consumer.
    nonisolated let events: AsyncStream<LiveCaptureEvent>

    init(factories: StageFactories = .live) {
        detector = factories.makeDetector()
        stabilizer = factories.makeStabilizer()
        rectifier = factories.makeRectifier()
        cutDetector = factories.makeCutDetector()

        let (stream, continuation) = AsyncStream.makeStream(of: LiveCaptureEvent.self)
        events = stream
        eventContinuation = continuation
    }

    /// Consumes the frame stream until it finishes (source stopped) or the
    /// surrounding task is cancelled.
    func run(frames: AsyncStream<CapturedFrame>) async {
        reset()
        for await frame in frames {
            if Task.isCancelled { break }
            processFrame(frame)
        }
        eventContinuation.finish()
    }

    func reset() {
        cutTimes.removeAll()
        stabilizer.reset()
        cutDetector.reset()
        screenLocked = false
    }

    // MARK: - Per-frame

    private func processFrame(_ frame: CapturedFrame) {
        let rawQuad = (try? detector.detectQuad(in: frame)) ?? nil
        let quad = stabilizer.stabilize(rawQuad, at: frame.timestamp)

        let locked = quad != nil
        if locked != screenLocked {
            screenLocked = locked
            eventContinuation.yield(.screenLock(locked))
        }
        guard let quad, let rectified = rectifier.rectify(frame, quad: quad) else {
            return
        }

        if cutDetector.process(rectified, at: frame.timestamp) {
            cutTimes.append(frame.timestamp)
            eventContinuation.yield(.cutDetected(atTime: frame.timestamp))
        }
    }
}
