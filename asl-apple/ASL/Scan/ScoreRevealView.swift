// ScoreRevealView.swift
// ASL
//
// Animated score reveal: the numeral counts up from 0 to the final value,
// then the label chip fades in. Pure presentation — the number shown is
// always the server's, rounded only for display.

import SwiftUI
import PacingKit

struct ScoreRevealView: View {
    let score: Double
    let label: PacingLabel

    @State private var displayedScore: Double = 0
    @State private var showChip = false

    var body: some View {
        VStack(spacing: 8) {
            CountUpText(value: displayedScore)
                .font(Theme.scoreFont)
                .foregroundStyle(Theme.scoreGradient)
                .accessibilityLabel("Pacing score \(Int(score.rounded())) out of 100")

            Text("pacing score · 0–100")
                .font(.caption)
                .foregroundStyle(.secondary)

            PacingLabelChip(label: label)
                .opacity(showChip ? 1 : 0)
        }
        .onAppear {
            withAnimation(.easeOut(duration: 1.2)) {
                displayedScore = score
            }
            withAnimation(.easeIn(duration: 0.3).delay(1.1)) {
                showChip = true
            }
        }
    }
}

/// Text whose numeric content participates in animation: SwiftUI interpolates
/// `animatableData`, re-rendering the rounded integer every frame.
private struct CountUpText: View, Animatable {
    var value: Double

    nonisolated var animatableData: Double {
        get { value }
        set { value = newValue }
    }

    var body: some View {
        Text("\(Int(value.rounded()))")
            .contentTransition(.identity)
    }
}
