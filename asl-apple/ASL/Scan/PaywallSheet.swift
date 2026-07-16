// PaywallSheet.swift
// ASL
//
// Shown on 402 (free scans exhausted) and from Settings. Never a dead-end:
// "Keep browsing" dismisses and routes to the always-free Browse tab. Pitch
// copy follows the neutral-instrument rule — it sells more measuring, not
// protection or outcomes.

import SwiftUI

struct PaywallSheet: View {
    @Environment(\.dismiss) private var dismiss
    @Environment(SubscriptionManager.self) private var subscriptions
    @Environment(AppRouter.self) private var router

    var body: some View {
        NavigationStack {
            VStack(spacing: 24) {
                VStack(spacing: 8) {
                    Image(systemName: "waveform.badge.magnifyingglass")
                        .font(.system(size: 44))
                        .foregroundStyle(Theme.scoreGradient)
                    Text("ASL Unlimited")
                        .font(.title.bold())
                    Text("You've used your 3 free scans.")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }

                VStack(alignment: .leading, spacing: 12) {
                    benefit(icon: "infinity", text: "Unlimited URL scans")
                    benefit(icon: "camera.metering.center.weighted",
                            text: "Live capture: measure any screen with your camera")
                    benefit(icon: "iphone",
                            text: "Live detection runs entirely on your iPhone")
                }
                .padding()
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(.quaternary.opacity(0.4), in: RoundedRectangle(cornerRadius: Theme.cardCornerRadius))

                Spacer()

                VStack(spacing: 12) {
                    Button {
                        Task {
                            if await subscriptions.purchase() {
                                dismiss()
                            }
                        }
                    } label: {
                        Group {
                            if subscriptions.isPurchasing {
                                ProgressView()
                            } else {
                                Text("Subscribe · \(subscriptions.displayPrice ?? "$9.99")/month")
                            }
                        }
                        .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.large)
                    .disabled(subscriptions.isPurchasing || subscriptions.monthlyProduct == nil)

                    Button("Restore purchases") {
                        Task {
                            await subscriptions.restore()
                            if subscriptions.isSubscribed { dismiss() }
                        }
                    }
                    .font(.subheadline)

                    // The escape hatch: charts stay free forever.
                    Button("Keep browsing the charts — free") {
                        dismiss()
                        router.selectedTab = .browse
                    }
                    .font(.subheadline)
                    .foregroundStyle(.secondary)

                    if let message = subscriptions.lastErrorMessage {
                        Text(message)
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                            .multilineTextAlignment(.center)
                    }

                    Text("Auto-renews monthly. Cancel anytime in Settings.")
                        .font(.caption2)
                        .foregroundStyle(.tertiary)
                }
            }
            .padding()
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Close") { dismiss() }
                }
            }
        }
        .presentationDetents([.large, .medium])
    }

    private func benefit(icon: String, text: String) -> some View {
        Label {
            Text(text).font(.subheadline)
        } icon: {
            Image(systemName: icon)
                .foregroundStyle(.tint)
        }
    }
}
