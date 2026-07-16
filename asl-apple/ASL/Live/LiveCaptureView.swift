// LiveCaptureView.swift
// ASL
//
// Live capture surface (paid, feature-flagged — the tab only exists when
// FeatureFlags.liveCaptureEnabled). Point the camera at any screen; cuts are
// detected on-device and ticked in real time.

import SwiftUI
import PacingKit

struct LiveCaptureView: View {
    @Environment(\.apiClient) private var api
    @Environment(SubscriptionManager.self) private var subscriptions
    @State private var controller = LiveSessionController()
    @State private var showPaywall = false

    var body: some View {
        NavigationStack {
            Group {
                if subscriptions.isSubscribed {
                    captureContent
                } else {
                    subscribeGate
                }
            }
            .navigationTitle("Live")
            .sheet(isPresented: $showPaywall) {
                PaywallSheet()
            }
        }
    }

    // MARK: - Paid gate

    private var subscribeGate: some View {
        VStack(spacing: 16) {
            Image(systemName: "camera.metering.center.weighted")
                .font(.system(size: 44))
                .foregroundStyle(.secondary)
            Text("Live capture is part of ASL Unlimited")
                .font(.headline)
            Text("Point your iPhone at any screen and measure its cutting rate in real time.")
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
            Button("See plans") { showPaywall = true }
                .buttonStyle(.borderedProminent)
        }
        .padding()
    }

    // MARK: - Capture

    @ViewBuilder
    private var captureContent: some View {
        switch controller.phase {
        case .idle, .starting, .capturing:
            captureStage
        case .finished(let summary), .submitting(let summary):
            LiveSummaryView(
                summary: summary,
                controller: controller,
                isSubmitting: {
                    if case .submitting = controller.phase { return true }
                    return false
                }()
            )
        case .submitted(let summary, let receipt):
            LiveSubmittedView(summary: summary, receipt: receipt) {
                controller.discard()
            }
        case .failed(let message):
            VStack(spacing: 12) {
                Label(message, systemImage: "exclamationmark.triangle")
                    .font(.subheadline)
                Button("OK") { controller.discard() }
                    .buttonStyle(.bordered)
            }
            .padding()
        }
    }

    private var captureStage: some View {
        VStack(spacing: 12) {
            ZStack {
                CameraPreviewView(provider: controller.previewSource)
                    .clipShape(RoundedRectangle(cornerRadius: Theme.cardCornerRadius))

                if controller.isCapturing && !controller.screenLocked {
                    Text("Aim at a screen")
                        .font(.subheadline.weight(.medium))
                        .padding(.horizontal, 14)
                        .padding(.vertical, 8)
                        .background(.ultraThinMaterial, in: Capsule())
                }

                CutTickOverlay(lastCutAt: controller.lastCutAt)
            }
            .frame(maxHeight: .infinity)

            if controller.isCapturing {
                HStack(spacing: 16) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text(String(format: "%.0f", controller.currentCutsPerMinute))
                            .font(.title2.bold().monospacedDigit())
                        Text("cuts/min (rolling)")
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                    }
                    SparklineView(samples: controller.rateSamples)
                        .frame(height: 36)
                    VStack(alignment: .trailing, spacing: 2) {
                        Text(Duration.seconds(controller.elapsed)
                            .formatted(.time(pattern: .minuteSecond)))
                            .font(.title2.bold().monospacedDigit())
                        Text("\(controller.cutTimes.count) cuts")
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                    }
                }
                .padding(.horizontal)
            }

            // Privacy line — verbatim product copy, always visible here.
            Label(
                "All detection runs on your iPhone. No video ever leaves the device.",
                systemImage: "lock.shield"
            )
            .font(.footnote)
            .foregroundStyle(.secondary)

            Button {
                if controller.isCapturing {
                    controller.stop()
                } else {
                    controller.start()
                }
            } label: {
                Text(controller.isCapturing ? "End session" : "Start measuring")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .tint(controller.isCapturing ? .red : .accentColor)
        }
        .padding()
    }
}

// MARK: - Post-session summary

private struct LiveSummaryView: View {
    let summary: CutSummary
    @Bindable var controller: LiveSessionController
    let isSubmitting: Bool

    @Environment(\.apiClient) private var api

    var body: some View {
        ScrollView {
            VStack(spacing: 20) {
                ScoreRevealView(score: summary.score, label: summary.label)

                HStack(spacing: 0) {
                    stat(String(format: "%.1fs", summary.medianShotS), "median shot")
                    Divider().frame(height: 32)
                    stat(String(format: "%.1f", summary.cutsPerMinute), "cuts/min")
                    Divider().frame(height: 32)
                    stat("\(summary.cutCount)", "cuts")
                    Divider().frame(height: 32)
                    stat(Duration.seconds(summary.durationS)
                        .formatted(.time(pattern: .minuteSecond)), "duration")
                }

                Picker("Content type", selection: $controller.contentLabel) {
                    ForEach(LiveSessionController.contentLabels, id: \.self) { label in
                        Text(label).tag(label)
                    }
                }
                .pickerStyle(.menu)

                if let error = controller.submissionError {
                    Text(error)
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }

                Button {
                    controller.submit(using: api)
                } label: {
                    Group {
                        if isSubmitting {
                            ProgressView()
                        } else {
                            Text("Submit session")
                        }
                    }
                    .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .disabled(isSubmitting)

                Button("Discard") { controller.discard() }
                    .font(.subheadline)
                    .foregroundStyle(.secondary)

                Text("Submitting sends only cut timestamps and duration — never video.")
                    .font(.caption2)
                    .foregroundStyle(.tertiary)
            }
            .padding()
        }
    }

    private func stat(_ value: String, _ caption: String) -> some View {
        VStack(spacing: 2) {
            Text(value).font(.headline.monospacedDigit())
            Text(caption).font(.caption2).foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
    }
}

private struct LiveSubmittedView: View {
    let summary: CutSummary
    let receipt: LiveSessionReceipt
    let onDone: () -> Void

    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: "checkmark.circle")
                .font(.system(size: 44))
                .foregroundStyle(.tint)
            Text("Session submitted")
                .font(.headline)
            if let serverScore = receipt.score {
                // Device and server run the same engine version over the same
                // cut times, so these should agree to ~1e-9.
                Text("Server score: \(Int(serverScore.rounded())) · device score: \(Int(summary.score.rounded()))")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }
            Button("Done", action: onDone)
                .buttonStyle(.borderedProminent)
        }
        .padding()
    }
}
