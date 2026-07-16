// Theme.swift
// ASL
//
// Visual language for the "neutral instrument" positioning. Deliberate rule:
// pacing labels never map onto a green→red "safe→dangerous" ramp. Each label
// gets a distinct, non-judgmental hue — the palette says "different", never
// "better/worse".

import SwiftUI
import PacingKit

enum Theme {
    // MARK: - Label colors (neutral by design)

    static func color(for label: PacingLabel) -> Color {
        switch label {
        case .calm: .teal
        case .moderate: .blue
        case .fast: .indigo
        case .hyperPaced: .purple
        }
    }

    static func color(forScore score: Double) -> Color {
        color(for: PacingEngine.label(forScore: score))
    }

    /// Gradient used behind big score numerals and on the share card.
    /// Cool-to-cool ramp, again avoiding any alarm-color connotation.
    static let scoreGradient = LinearGradient(
        colors: [.teal, .blue, .indigo, .purple],
        startPoint: .leading,
        endPoint: .trailing
    )

    // MARK: - Typography & metrics

    static let scoreFont = Font.system(size: 72, weight: .bold, design: .rounded)
        .monospacedDigit()

    static let cardCornerRadius: CGFloat = 16
    static let heatmapStripHeight: CGFloat = 56
}

// MARK: - Shared label chip

/// Capsule chip for a pacing label ("calm" / "moderate" / "fast" /
/// "hyper-paced"). Copy is the label itself — no adjectives added.
struct PacingLabelChip: View {
    let label: PacingLabel

    var body: some View {
        Text(label.rawValue)
            .font(.subheadline.weight(.semibold))
            .padding(.horizontal, 12)
            .padding(.vertical, 5)
            .background(Theme.color(for: label).opacity(0.18), in: Capsule())
            .foregroundStyle(Theme.color(for: label))
            .accessibilityLabel("Pacing label: \(label.rawValue)")
    }
}
