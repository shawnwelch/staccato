// LiveSessionController.swift
// ASL
//
// Main-actor session lifecycle for live capture:
//   idle → starting → capturing (cuts stream in) → finished (PacingKit
//   summary) → submitting → submitted
//
// The score shown at session end is computed ON DEVICE via PacingKit — the
// same engine version the server runs, so the number the user sees equals
// the number the server recomputes from the submitted cut times.

import AVFoundation
import Foundation
import Observation
import PacingKit

/// Narrow surface the preview layer needs; keeps views from touching the
/// frame source directly.
protocol CaptureSessionProviding {
    var captureSession: AVCaptureSession { get }
}

extension CameraFrameSource: CaptureSessionProviding {}

@MainActor
@Observable
final class LiveSessionController {

    enum Phase: Equatable {
        case idle
        case starting
        case capturing
        case finished(CutSummary)
        case submitting(CutSummary)
        case submitted(CutSummary, receipt: LiveSessionReceipt)
        case failed(message: String)
    }

    /// Neutral content-category tags for a submission (context for browsing,
    /// never a judgment).
    static let contentLabels = ["animation", "live-action", "gaming", "sports", "music-video", "other"]

    private(set) var phase: Phase = .idle
    private(set) var screenLocked = false
    private(set) var cutTimes: [Double] = []
    /// Rolling cuts/min samples (one per second) feeding the sparkline.
    private(set) var rateSamples: [Double] = []
    /// Wall-clock moment of the most recent cut (drives the tick flash).
    private(set) var lastCutAt: Date?
    private(set) var elapsed: TimeInterval = 0
    private(set) var submissionError: String?
    var contentLabel = "other"

    /// Trailing window for the live cuts/min readout.
    private let rateWindow: TimeInterval = 30

    private let frameSource: CameraFrameSource
    private var engine: LiveCaptureEngine?
    private var pipelineTask: Task<Void, Never>?
    private var eventTask: Task<Void, Never>?
    private var tickerTask: Task<Void, Never>?
    private var sessionStart: Date?

    var previewSource: any CaptureSessionProviding { frameSource }

    init(frameSource: CameraFrameSource = CameraFrameSource()) {
        self.frameSource = frameSource
    }

    var isCapturing: Bool { phase == .capturing || phase == .starting }

    var currentCutsPerMinute: Double { rateSamples.last ?? 0 }

    // MARK: - Lifecycle

    func start() {
        guard !isCapturing else { return }
        phase = .starting
        cutTimes = []
        rateSamples = []
        lastCutAt = nil
        elapsed = 0
        submissionError = nil

        let engine = LiveCaptureEngine()
        self.engine = engine

        // Pipeline events → UI state. Task inherits the main actor, so state
        // mutation here is ordinary property access.
        eventTask = Task { [weak self] in
            for await event in engine.events {
                guard let self else { return }
                switch event {
                case .screenLock(let locked):
                    self.screenLocked = locked
                case .cutDetected(let t):
                    self.cutTimes.append(t)
                    self.lastCutAt = Date()
                }
            }
        }

        sessionStart = Date()
        pipelineTask = Task { [frameSource] in
            do {
                let frames = try await frameSource.start()
                self.phase = .capturing
                self.startTicker()
                await engine.run(frames: frames) // returns when the stream ends
            } catch {
                self.phase = .failed(message: Self.message(forStartError: error))
            }
        }
    }

    func stop() {
        guard isCapturing else { return }
        tickerTask?.cancel()
        tickerTask = nil
        if let start = sessionStart {
            elapsed = Date().timeIntervalSince(start)
        }

        let duration = elapsed
        Task {
            await frameSource.stop() // finishes the frame stream → engine.run returns
            eventTask?.cancel()

            guard duration > 0 else {
                phase = .failed(message: "Session was too short to score.")
                return
            }
            // Read cutTimes only after the source stopped, so trailing cut
            // events have all been applied.
            // Same engine, same version, as the backend — see PacingKit.
            let summary = PacingEngine.summarize(cutTimes: cutTimes, duration: duration)
            phase = .finished(summary)
        }
    }

    func discard() {
        phase = .idle
        cutTimes = []
        rateSamples = []
        elapsed = 0
        submissionError = nil
    }

    // MARK: - Submission

    /// POST /v1/live-sessions. Only cut TIMESTAMPS and the summary travel —
    /// no image data exists to send. The server recomputes the score from
    /// cut_times_s; device_score is drift telemetry only.
    func submit(using api: APIClient) {
        guard case .finished(let summary) = phase else { return }
        phase = .submitting(summary)
        submissionError = nil
        let submission = LiveSessionSubmission(
            cutTimesS: cutTimes.filter { $0 > 0 && $0 < summary.durationS },
            durationS: summary.durationS,
            deviceScore: summary.score,
            contentLabel: contentLabel
        )
        Task {
            do {
                let receipt = try await api.submitLiveSession(submission)
                phase = .submitted(summary, receipt: receipt)
            } catch let error as APIClient.APIError {
                // Keep the local result — the measurement isn't lost just
                // because the upload was.
                phase = .finished(summary)
                submissionError = error.userMessage
            } catch {
                phase = .finished(summary)
                submissionError = "Couldn't submit the session. Try again."
            }
        }
    }

    // MARK: - Ticker (1 Hz)

    private func startTicker() {
        tickerTask = Task { [weak self] in
            while !Task.isCancelled {
                try? await Task.sleep(for: .seconds(1))
                guard let self, self.phase == .capturing else { continue }
                if let start = self.sessionStart {
                    self.elapsed = Date().timeIntervalSince(start)
                }
                self.rateSamples.append(self.rollingRate())
                if self.rateSamples.count > 180 { // keep ~3 min of sparkline
                    self.rateSamples.removeFirst()
                }
            }
        }
    }

    /// Cuts/min over the trailing window, clipped to session start (the same
    /// clipped-window normalization idea as the engine's heat map).
    private func rollingRate() -> Double {
        let now = elapsed
        let lo = max(0, now - rateWindow)
        let span = now - lo
        guard span > 0 else { return 0 }
        let count = cutTimes.filter { $0 >= lo && $0 < now }.count
        return Double(count) / span * 60.0
    }

    private static func message(forStartError error: Error) -> String {
        if let cameraError = error as? CameraFrameSource.CameraError {
            switch cameraError {
            case .permissionDenied:
                return "Camera access is off. Enable it in Settings to use live capture."
            case .noCamera:
                return "No camera available on this device."
            case .configurationFailed:
                return "The camera couldn't be configured."
            }
        }
        return "Couldn't start the camera."
    }
}
