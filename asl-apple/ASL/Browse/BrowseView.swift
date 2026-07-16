// BrowseView.swift
// ASL
//
// Leaderboard of channel pacing scores. Always free and always reachable —
// this tab is the guaranteed non-dead-end when the scan quota runs out.
// Presentation stays neutral: scores and trends are shown as measurements;
// nothing is ranked as "better" or "worse", just faster or slower.

import SwiftUI
import PacingKit

struct BrowseView: View {
    @Environment(\.apiClient) private var api

    enum LoadState {
        case loading
        case loaded(Leaderboard)
        case failed(String)
    }

    @State private var state: LoadState = .loading
    @State private var category: String?

    var body: some View {
        NavigationStack {
            Group {
                switch state {
                case .loading:
                    ProgressView("Loading charts…")
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                case .failed(let message):
                    ContentUnavailableView {
                        Label("Charts unavailable", systemImage: "chart.bar.xaxis")
                    } description: {
                        Text(message)
                    } actions: {
                        Button("Retry") {
                            Task { await load() }
                        }
                    }
                case .loaded(let leaderboard):
                    leaderboardList(leaderboard)
                }
            }
            .navigationTitle("Browse")
            .navigationDestination(for: LeaderboardItem.self) { item in
                ChannelDetailView(channelID: item.channelId, channelTitle: item.title)
            }
            .task(id: category) {
                await load()
            }
        }
    }

    private func leaderboardList(_ leaderboard: Leaderboard) -> some View {
        List {
            if !leaderboard.categories.isEmpty {
                Picker("Category", selection: $category) {
                    Text("All").tag(String?.none)
                    ForEach(leaderboard.categories, id: \.self) { cat in
                        Text(cat).tag(String?.some(cat))
                    }
                }
                .pickerStyle(.menu)
            }

            ForEach(leaderboard.items) { item in
                NavigationLink(value: item) {
                    LeaderboardRow(item: item)
                }
            }

            Text("Channel score = median video score over recent uploads · Engine v\(PacingEngine.engineVersion)")
                .font(.caption2)
                .foregroundStyle(.tertiary)
                .listRowSeparator(.hidden)
        }
        .listStyle(.plain)
        .refreshable { await load() }
    }

    private func load() async {
        if case .loaded = state {} else { state = .loading }
        do {
            let leaderboard = try await api.leaderboard(category: category)
            state = .loaded(leaderboard)
        } catch let error as APIClient.APIError {
            state = .failed(error.userMessage)
        } catch {
            state = .failed("Couldn't load the charts. Try again in a moment.")
        }
    }
}

// MARK: - Row

private struct LeaderboardRow: View {
    let item: LeaderboardItem

    var body: some View {
        HStack(spacing: 12) {
            Text("\(item.rank)")
                .font(.subheadline.monospacedDigit())
                .foregroundStyle(.secondary)
                .frame(width: 32, alignment: .trailing)

            VStack(alignment: .leading, spacing: 2) {
                Text(item.title)
                    .font(.body)
                    .lineLimit(1)
                HStack(spacing: 6) {
                    if let category = item.category {
                        Text(category)
                    }
                    if let subs = item.subscriberCount {
                        Text("\(subs.formatted(.number.notation(.compactName))) subs")
                    }
                    Text("\(item.nVideos) videos")
                }
                .font(.caption)
                .foregroundStyle(.secondary)
            }

            Spacer()

            // Trend arrow: direction only, deliberately monochrome —
            // speeding up is not "worse", slowing down is not "better".
            Image(systemName: item.trend.systemImage)
                .font(.caption)
                .foregroundStyle(.secondary)
                .accessibilityLabel("Trend: \(item.trend.displayName)")

            Text("\(Int(item.score.rounded()))")
                .font(.headline.monospacedDigit())
                .foregroundStyle(Theme.color(forScore: item.score))
                .frame(width: 40, alignment: .trailing)
        }
    }
}
