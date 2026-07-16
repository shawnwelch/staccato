// ScanView.swift
// ASL
//
// Paste-a-URL scan flow. Copy rule for this whole surface: describe what is
// measured ("shot changes per minute"), never effects on viewers.

import SwiftUI
import UIKit // UIPasteboard

struct ScanView: View {
    @Environment(\.apiClient) private var api
    @Environment(AppRouter.self) private var router
    @State private var model = ScanViewModel()

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 24) {
                    inputSection
                    statusSection
                }
                .padding()
            }
            .navigationTitle("Scan")
            .sheet(isPresented: $model.showPaywall) {
                PaywallSheet()
            }
            .task {
                await model.syncQuota(from: api)
            }
            .onChange(of: router.pendingScanURL, initial: true) { _, url in
                guard let url else { return }
                model.adopt(pendingURL: url)
                router.pendingScanURL = nil
            }
        }
    }

    // MARK: - Input

    private var inputSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Measure a video's cutting rate")
                .font(.title2.bold())
            Text("Paste a video link. ASL measures how often the shot changes and returns a 0–100 pacing score.")
                .font(.subheadline)
                .foregroundStyle(.secondary)

            HStack(spacing: 8) {
                TextField("https://youtube.com/watch?v=…", text: $model.urlText)
                    .textFieldStyle(.roundedBorder)
                    .keyboardType(.URL)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .submitLabel(.go)
                    .onSubmit { model.submit(using: api) }

                Button {
                    if let pasted = UIPasteboard.general.string {
                        model.urlText = pasted
                    }
                } label: {
                    Image(systemName: "doc.on.clipboard")
                }
                .buttonStyle(.bordered)
                .accessibilityLabel("Paste from clipboard")
            }

            Label(
                "Tip: you can also share a video straight from the YouTube app — tap Share, then \"Scan with ASL\".",
                systemImage: "square.and.arrow.up"
            )
            .font(.footnote)
            .foregroundStyle(.secondary)

            Button {
                model.submit(using: api)
            } label: {
                if model.isBusy {
                    ProgressView().frame(maxWidth: .infinity)
                } else {
                    Text("Scan").frame(maxWidth: .infinity)
                }
            }
            .buttonStyle(.borderedProminent)
            .disabled(!model.canSubmit)

            // Quota display is server-reported only — we show the number the
            // backend gave us or nothing at all.
            if let remaining = model.scansRemaining {
                Text(remaining == 1
                     ? "1 free scan remaining"
                     : "\(remaining) free scans remaining")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }
        }
    }

    // MARK: - Status / result

    @ViewBuilder
    private var statusSection: some View {
        switch model.phase {
        case .idle:
            EmptyView()

        case .submitting:
            progressCard(text: "Sending link…")

        case .polling:
            progressCard(text: "Analyzing — detecting shot changes…")

        case .complete(let analysis):
            ScanResultView(analysis: analysis) {
                model.reset()
            }

        case .failed(let message):
            VStack(alignment: .leading, spacing: 8) {
                Label(message, systemImage: "exclamationmark.triangle")
                    .font(.subheadline)
                Button("Try again") { model.reset() }
                    .buttonStyle(.bordered)
            }
            .padding()
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(.quaternary.opacity(0.5), in: RoundedRectangle(cornerRadius: Theme.cardCornerRadius))
        }
    }

    private func progressCard(text: String) -> some View {
        HStack(spacing: 12) {
            ProgressView()
            Text(text)
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
        .padding()
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.quaternary.opacity(0.5), in: RoundedRectangle(cornerRadius: Theme.cardCornerRadius))
    }
}

// MARK: - Result

private struct ScanResultView: View {
    let analysis: Analysis
    let onScanAnother: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            if let score = analysis.score, let label = analysis.label {
                ScoreRevealView(score: score, label: label)
                    .frame(maxWidth: .infinity)
            }

            if let heatmapURL = analysis.heatmapPngUrl {
                HeatmapStripView(url: heatmapURL)
            }

            metricsRow

            ShareScoreSection(analysis: analysis)

            Button("Scan another video", action: onScanAnother)
                .buttonStyle(.bordered)
                .frame(maxWidth: .infinity)
        }
        .padding()
        .background(.quaternary.opacity(0.4), in: RoundedRectangle(cornerRadius: Theme.cardCornerRadius))
    }

    private var metricsRow: some View {
        HStack(spacing: 0) {
            metric(
                value: analysis.medianShotS.map { String(format: "%.1fs", $0) } ?? "—",
                caption: "median shot")
            Divider().frame(height: 32)
            metric(
                value: analysis.cutsPerMinute.map { String(format: "%.1f", $0) } ?? "—",
                caption: "cuts/min")
            Divider().frame(height: 32)
            metric(
                value: analysis.cutCount.map(String.init) ?? "—",
                caption: "cuts")
        }
    }

    private func metric(value: String, caption: String) -> some View {
        VStack(spacing: 2) {
            Text(value).font(.headline.monospacedDigit())
            Text(caption).font(.caption2).foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
    }
}
