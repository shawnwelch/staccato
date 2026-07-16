// SettingsView.swift
// ASL

import StoreKit
import SwiftUI
import PacingKit

struct SettingsView: View {
    @Environment(ClerkSession.self) private var session
    @Environment(SubscriptionManager.self) private var subscriptions
    @Environment(\.openURL) private var openURL

    @State private var showManageSubscriptions = false
    @State private var showPaywall = false

    var body: some View {
        NavigationStack {
            Form {
                accountSection
                subscriptionSection
                aboutSection
            }
            .navigationTitle("Settings")
            .manageSubscriptionsSheet(isPresented: $showManageSubscriptions)
            .sheet(isPresented: $showPaywall) {
                PaywallSheet()
            }
        }
    }

    // MARK: - Account

    private var accountSection: some View {
        Section("Account") {
            if let profile = session.profile {
                LabeledContent("Signed in as", value: profile.email ?? profile.userID)
                Button("Sign out", role: .destructive) {
                    Task { await session.signOut() }
                }
            } else {
                // TODO(clerk): replace with Clerk's sign-in UI once the SDK
                // is wired (see ClerkSession.swift).
                LabeledContent("Status", value: "Signed out")
                Button("Sign in") {
                    Task { await session.signIn() }
                }
                if let message = session.lastErrorMessage {
                    Text(message)
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
            }
        }
    }

    // MARK: - Subscription

    private var subscriptionSection: some View {
        Section("Subscription") {
            if subscriptions.isSubscribed {
                LabeledContent("Plan", value: "ASL Unlimited")
                Button("Manage subscription") {
                    showManageSubscriptions = true
                }
            } else {
                LabeledContent("Plan", value: "Free · 3 scans")
                Button("Get ASL Unlimited") {
                    showPaywall = true
                }
                Button("Restore purchases") {
                    Task { await subscriptions.restore() }
                }
            }
        }
    }

    // MARK: - About

    private var aboutSection: some View {
        Section("About") {
            // The engine version is the parity contract with the backend:
            // identical inputs produce identical scores on both.
            LabeledContent("Engine", value: "v\(PacingEngine.engineVersion)")

            if let methodology = AppConfig.methodologyURL {
                Button("How scores are measured") {
                    openURL(methodology)
                }
            }

            // Positioning, verbatim: measurement only, no effect claims.
            Text("ASL measures how often a video changes shots. It reports pacing — calm, moderate, fast, hyper-paced — and makes no claims about effects on viewers.")
                .font(.footnote)
                .foregroundStyle(.secondary)
        }
    }
}
