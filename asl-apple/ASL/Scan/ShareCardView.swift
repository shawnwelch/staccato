// ShareCardView.swift
// ASL
//
// Sharing a result exports two representations in a single Transferable:
//   1. the public share-page URL (https://{frontend}/s/{slug}) — most
//      receivers (Messages, Mail, socials) take this;
//   2. a PNG score card rendered with ImageRenderer — image-first receivers
//      (Photos, Instagram) take this.

import SwiftUI
import UIKit // UIImage (ImageRenderer output → PNG data)
import UniformTypeIdentifiers
import PacingKit

// MARK: - Transferable payload

struct ScoreShareItem: Transferable {
    let url: URL
    let pngData: Data
    let title: String

    static var transferRepresentation: some TransferRepresentation {
        // Order matters: URL first so link-preferring receivers pick it.
        ProxyRepresentation(exporting: \.url)
        DataRepresentation(exportedContentType: .png) { item in item.pngData }
    }
}

// MARK: - Share section (button + renderer)

struct ShareScoreSection: View {
    let analysis: Analysis

    @State private var shareItem: ScoreShareItem?

    var body: some View {
        Group {
            if let shareItem {
                ShareLink(
                    item: shareItem,
                    preview: SharePreview(
                        shareItem.title,
                        image: Image(systemName: "waveform.badge.magnifyingglass")
                    )
                ) {
                    Label("Share score", systemImage: "square.and.arrow.up")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
            }
        }
        .task(id: analysis.id) {
            shareItem = Self.makeShareItem(for: analysis)
        }
    }

    /// Builds the payload; returns nil when the analysis has no share page
    /// yet (the button simply doesn't appear rather than sharing a dead link).
    @MainActor
    private static func makeShareItem(for analysis: Analysis) -> ScoreShareItem? {
        guard
            let slug = analysis.shareSlug,
            let url = AppConfig.shareURL(slug: slug),
            let score = analysis.score,
            let label = analysis.label
        else { return nil }

        let renderer = ImageRenderer(content: ScoreCardView(score: score, label: label))
        renderer.scale = 3 // crisp on retina when saved/shared
        guard let uiImage = renderer.uiImage, let png = uiImage.pngData() else {
            return nil
        }
        return ScoreShareItem(
            url: url,
            pngData: png,
            title: "ASL pacing score: \(Int(score.rounded())) (\(label.rawValue))"
        )
    }
}

// MARK: - The card itself

/// Fixed-size card rendered off-screen by ImageRenderer. Copy stays
/// measurement-only: score, label, and what ASL is — no claims.
struct ScoreCardView: View {
    let score: Double
    let label: PacingLabel

    var body: some View {
        VStack(spacing: 16) {
            Text("ASL")
                .font(.headline.weight(.heavy))
                .tracking(4)
                .foregroundStyle(.secondary)

            Text("\(Int(score.rounded()))")
                .font(.system(size: 120, weight: .bold, design: .rounded))
                .monospacedDigit()
                .foregroundStyle(Theme.scoreGradient)

            Text("pacing score · 0–100")
                .font(.subheadline)
                .foregroundStyle(.secondary)

            PacingLabelChip(label: label)

            Text("Measures how often the shot changes.")
                .font(.footnote)
                .foregroundStyle(.tertiary)
        }
        .padding(40)
        .frame(width: 400, height: 440)
        .background(Color(.systemBackground))
    }
}
