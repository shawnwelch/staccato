// RootTabView.swift
// ASL

import SwiftUI

struct RootTabView: View {
    @Environment(AppRouter.self) private var router

    var body: some View {
        @Bindable var router = router
        TabView(selection: $router.selectedTab) {
            Tab("Scan", systemImage: "waveform.badge.magnifyingglass", value: AppRouter.Tab.scan) {
                ScanView()
            }

            // Live capture ships dark: the tab simply doesn't exist until the
            // flag flips. Inside, it is additionally gated on subscription.
            if FeatureFlags.liveCaptureEnabled {
                Tab("Live", systemImage: "camera.metering.center.weighted", value: AppRouter.Tab.live) {
                    LiveCaptureView()
                }
            }

            Tab("Browse", systemImage: "chart.bar.xaxis", value: AppRouter.Tab.browse) {
                BrowseView()
            }

            Tab("Settings", systemImage: "gearshape", value: AppRouter.Tab.settings) {
                SettingsView()
            }
        }
    }
}
