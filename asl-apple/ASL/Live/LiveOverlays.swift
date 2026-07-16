// LiveOverlays.swift
// ASL
//
// Camera preview wrapper + the two live readouts: a per-cut tick flash and a
// rolling cuts/min sparkline (Canvas).

import AVFoundation
import SwiftUI
import UIKit

// MARK: - Camera preview

struct CameraPreviewView: UIViewRepresentable {
    let provider: any CaptureSessionProviding

    final class PreviewUIView: UIView {
        override static var layerClass: AnyClass { AVCaptureVideoPreviewLayer.self }
        var previewLayer: AVCaptureVideoPreviewLayer {
            layer as! AVCaptureVideoPreviewLayer
        }
    }

    func makeUIView(context: Context) -> PreviewUIView {
        let view = PreviewUIView()
        view.previewLayer.session = provider.captureSession
        view.previewLayer.videoGravity = .resizeAspectFill
        return view
    }

    func updateUIView(_ uiView: PreviewUIView, context: Context) {
        if uiView.previewLayer.session !== provider.captureSession {
            uiView.previewLayer.session = provider.captureSession
        }
    }
}

// MARK: - Cut tick flash

/// A visible tick on every detected cut: a ring that pops and fades over
/// ~0.4s. Driven purely by `lastCutAt` changing, so it needs no timers of
/// its own.
struct CutTickOverlay: View {
    let lastCutAt: Date?

    var body: some View {
        TimelineView(.animation(minimumInterval: 1.0 / 60.0, paused: lastCutAt == nil)) { timeline in
            let progress = flashProgress(now: timeline.date)
            if let progress {
                RoundedRectangle(cornerRadius: Theme.cardCornerRadius)
                    .stroke(Color.white.opacity(0.9 * (1 - progress)), lineWidth: 4)
                    .padding(2)
                    .overlay(alignment: .top) {
                        Text("cut")
                            .font(.caption.weight(.bold).monospaced())
                            .padding(.horizontal, 8)
                            .padding(.vertical, 3)
                            .background(.black.opacity(0.6 * (1 - progress)), in: Capsule())
                            .foregroundStyle(.white.opacity(1 - progress))
                            .padding(.top, 10)
                    }
            }
        }
        .allowsHitTesting(false)
        .accessibilityHidden(true)
    }

    private func flashProgress(now: Date) -> Double? {
        guard let lastCutAt else { return nil }
        let age = now.timeIntervalSince(lastCutAt)
        let duration = 0.4
        guard age >= 0, age < duration else { return nil }
        return age / duration
    }
}

// MARK: - Sparkline

/// Rolling cuts/min line, one sample per second. Pure Canvas — no Charts
/// dependency here because this redraws every second during capture and a
/// polyline is all that's needed.
struct SparklineView: View {
    let samples: [Double]

    var body: some View {
        Canvas { context, size in
            guard samples.count > 1 else { return }

            // Fixed-ish scale with headroom so the line doesn't rescale
            // distractingly on every new sample.
            let maxValue = max(samples.max() ?? 0, 30)
            let stepX = size.width / CGFloat(samples.count - 1)

            func point(at index: Int) -> CGPoint {
                let clamped = min(samples[index], maxValue)
                let y = size.height - CGFloat(clamped / maxValue) * size.height
                return CGPoint(x: CGFloat(index) * stepX, y: y)
            }

            var line = Path()
            line.move(to: point(at: 0))
            for i in 1..<samples.count {
                line.addLine(to: point(at: i))
            }
            context.stroke(
                line,
                with: .color(.accentColor),
                style: StrokeStyle(lineWidth: 2, lineCap: .round, lineJoin: .round)
            )

            // Soft fill under the line.
            var fill = line
            fill.addLine(to: CGPoint(x: size.width, y: size.height))
            fill.addLine(to: CGPoint(x: 0, y: size.height))
            fill.closeSubpath()
            context.fill(fill, with: .color(.accentColor.opacity(0.12)))
        }
        .accessibilityLabel("Rolling cuts per minute")
        .accessibilityValue(String(format: "%.0f", samples.last ?? 0))
    }
}
