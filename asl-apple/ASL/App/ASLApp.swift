// ASLApp.swift
// ASL
//
// Composition root. Long-lived dependencies are created once here and flow
// down via the environment: observable models with .environment(_:), and the
// (non-observable) APIClient actor via a custom environment key.

import SwiftUI

// MARK: - Cross-tab routing

/// Navigation intents that cross tab boundaries (deep links, share-extension
/// handoff, "keep browsing" from the paywall).
@MainActor
@Observable
final class AppRouter {
    enum Tab: Hashable {
        case scan, live, browse, settings
    }

    var selectedTab: Tab = .scan

    /// URL waiting to be prefilled into the Scan tab (from a deep link or the
    /// share extension). ScanView consumes and clears it.
    var pendingScanURL: URL?

    func handle(_ link: DeepLink) {
        switch link {
        case .scan(let videoURL):
            if let videoURL { pendingScanURL = videoURL }
            selectedTab = .scan
        }
    }
}

// MARK: - APIClient in the environment

extension EnvironmentValues {
    /// Default is a token-less client so previews work offline; the real app
    /// overrides this in ASLApp with a Clerk-backed client.
    @Entry var apiClient = APIClient(
        baseURL: AppConfig.apiBaseURL,
        tokenProvider: StubTokenProvider()
    )
}

// MARK: - App

@main
struct ASLApp: App {
    @State private var session: ClerkSession
    @State private var subscriptions = SubscriptionManager()
    @State private var router = AppRouter()
    @Environment(\.scenePhase) private var scenePhase

    /// Actor, not observable — held once and injected via the environment.
    private let apiClient: APIClient

    private let pendingScans = PendingScanStore()

    init() {
        let session = ClerkSession()
        _session = State(initialValue: session)
        apiClient = APIClient(baseURL: AppConfig.apiBaseURL, tokenProvider: session)
    }

    var body: some Scene {
        WindowGroup {
            RootTabView()
                .environment(session)
                .environment(subscriptions)
                .environment(router)
                .environment(\.apiClient, apiClient)
                .task {
                    await subscriptions.start()
                }
                .onOpenURL { url in
                    if let link = DeepLink.parse(url) {
                        router.handle(link)
                    }
                }
                .onChange(of: scenePhase, initial: true) { _, phase in
                    // The share extension drops URLs into the app group; pick
                    // them up whenever we come to the foreground.
                    guard phase == .active else { return }
                    if let url = pendingScans.consume() {
                        router.pendingScanURL = url
                        router.selectedTab = .scan
                    }
                }
        }
    }
}
