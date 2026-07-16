// CameraFrameSource.swift
// ASL
//
// AVCaptureSession-backed FrameSource: rear wide camera, 30 fps, 4:2:0
// bi-planar output, late frames discarded. Frames flow out through an
// AsyncStream so the consumer (LiveCaptureEngine) is queue-agnostic.

@preconcurrency import AVFoundation
import CoreMedia
import Foundation

/// All mutable state is confined to `sessionQueue` (configuration, start/stop)
/// or the delegate callback (which AVFoundation serializes onto that same
/// queue) — hence `@unchecked Sendable`.
final class CameraFrameSource: NSObject, FrameSource, @unchecked Sendable {

    enum CameraError: Error {
        case permissionDenied
        case noCamera
        case configurationFailed
    }

    /// Exposed for AVCaptureVideoPreviewLayer only. Do not mutate outside
    /// this class.
    let captureSession = AVCaptureSession()

    private let sessionQueue = DispatchQueue(label: "asl.camera.session")
    private let videoOutput = AVCaptureVideoDataOutput()

    private var continuation: AsyncStream<CapturedFrame>.Continuation?
    private var firstFrameTime: CMTime?
    private var isConfigured = false

    // MARK: - FrameSource

    func start() async throws -> AsyncStream<CapturedFrame> {
        guard await Self.requestPermission() else {
            throw CameraError.permissionDenied
        }

        let (stream, continuation) = AsyncStream.makeStream(
            of: CapturedFrame.self,
            bufferingPolicy: .bufferingNewest(2) // drop stale frames, never block capture
        )

        try await withCheckedThrowingContinuation { (done: CheckedContinuation<Void, Error>) in
            sessionQueue.async {
                do {
                    try self.configureIfNeeded()
                    self.firstFrameTime = nil
                    self.continuation = continuation
                    self.captureSession.startRunning()
                    done.resume()
                } catch {
                    done.resume(throwing: error)
                }
            }
        }
        return stream
    }

    func stop() async {
        await withCheckedContinuation { (done: CheckedContinuation<Void, Never>) in
            sessionQueue.async {
                self.captureSession.stopRunning()
                self.continuation?.finish()
                self.continuation = nil
                done.resume()
            }
        }
    }

    // MARK: - Configuration (sessionQueue only)

    private func configureIfNeeded() throws {
        guard !isConfigured else { return }

        captureSession.beginConfiguration()
        defer { captureSession.commitConfiguration() }

        captureSession.sessionPreset = .hd1280x720

        guard let device = AVCaptureDevice.default(
            .builtInWideAngleCamera, for: .video, position: .back
        ) else { throw CameraError.noCamera }

        let input = try AVCaptureDeviceInput(device: device)
        guard captureSession.canAddInput(input) else { throw CameraError.configurationFailed }
        captureSession.addInput(input)

        // Lock to 30 fps: the cut detector's temporal statistics assume a
        // steady frame cadence.
        try device.lockForConfiguration()
        let frameDuration = CMTime(value: 1, timescale: 30)
        device.activeVideoMinFrameDuration = frameDuration
        device.activeVideoMaxFrameDuration = frameDuration
        device.unlockForConfiguration()

        videoOutput.videoSettings = [
            kCVPixelBufferPixelFormatTypeKey as String:
                kCVPixelFormatType_420YpCbCr8BiPlanarFullRange
        ]
        videoOutput.alwaysDiscardsLateVideoFrames = true
        videoOutput.setSampleBufferDelegate(self, queue: sessionQueue)
        guard captureSession.canAddOutput(videoOutput) else { throw CameraError.configurationFailed }
        captureSession.addOutput(videoOutput)

        isConfigured = true
    }

    private static func requestPermission() async -> Bool {
        switch AVCaptureDevice.authorizationStatus(for: .video) {
        case .authorized:
            return true
        case .notDetermined:
            return await AVCaptureDevice.requestAccess(for: .video)
        default:
            return false
        }
    }
}

// MARK: - Capture delegate (sessionQueue)

extension CameraFrameSource: AVCaptureVideoDataOutputSampleBufferDelegate {
    func captureOutput(
        _ output: AVCaptureOutput,
        didOutput sampleBuffer: CMSampleBuffer,
        from connection: AVCaptureConnection
    ) {
        guard
            let continuation,
            let pixelBuffer = CMSampleBufferGetImageBuffer(sampleBuffer)
        else { return }

        let presentation = CMSampleBufferGetPresentationTimeStamp(sampleBuffer)
        if firstFrameTime == nil { firstFrameTime = presentation }
        guard let firstFrameTime else { return }

        let timestamp = CMTimeGetSeconds(CMTimeSubtract(presentation, firstFrameTime))
        continuation.yield(CapturedFrame(pixelBuffer: pixelBuffer, timestamp: timestamp))
    }
}
