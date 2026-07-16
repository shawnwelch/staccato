// ChannelDetailView.swift
// ASL
//
// Channel page: current score, trend, and a per-video score history chart
// (SwiftUI Charts). Chart y-axis is always 0–100 so shapes are comparable
// across channels.

import Charts
import SwiftUI
import PacingKit

struct ChannelDetailView: View {
    let channelID: String
    let channelTitle: String

    @Environment(\.apiClient) private var api

    enum LoadState {
        case loading
        case loaded(Channel)
        case failed(String)
    }

    @State private var state: LoadState = .loading

    var body: some View {
        Group {
            switch state {
            case .loading:
                ProgressView()
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            case .failed(let message):
                ContentUnavailableView {
                    Label("Channel unavailable", systemImage: "tv")
                } description: {
                    Text(message)
                } actions: {
                    Button("Retry") { Task { await load() } }
                }
            case .loaded(let channel):
                content(channel)
            }
        }
        .navigationTitle(channelTitle)
        .navigationBarTitleDisplayMode(.inline)
        .task { await load() }
    }

    // MARK: - Content

    private func content(_ channel: Channel) -> some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                header(channel)

                if let score = channel.score {
                    scoreCard(score)
                    if !score.series.isEmpty {
                        historyChart(score.series)
                        recentVideos(score.series)
                    }
                } else {
                    Text("No score yet — not enough analyzed videos.")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
            }
            .padding()
        }
    }

    private func header(_ channel: Channel) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(channel.title)
                .font(.title2.bold())
            HStack(spacing: 8) {
                if let category = channel.category {
                    Text(category)
                }
                if let subs = channel.subscriberCount {
                    Text("\(subs.formatted(.number.notation(.compactName))) subscribers")
                }
            }
            .font(.subheadline)
            .foregroundStyle(.secondary)
        }
    }

    private func scoreCard(_ score: ChannelScore) -> some View {
        HStack(spacing: 16) {
            VStack(alignment: .leading, spacing: 2) {
                Text("\(Int(score.score.rounded()))")
                    .font(.system(size: 44, weight: .bold, design: .rounded))
                    .monospacedDigit()
                    .foregroundStyle(Theme.color(forScore: score.score))
                PacingLabelChip(label: PacingEngine.label(forScore: score.score))
            }
            Spacer()
            VStack(alignment: .trailing, spacing: 4) {
                Label(score.trend.displayName, systemImage: score.trend.systemImage)
                    .font(.subheadline)
                Text("median of \(score.nVideos) videos")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Text("Engine v\(score.engineVersion)")
                    .font(.caption2)
                    .foregroundStyle(.tertiary)
            }
        }
        .padding()
        .background(.quaternary.opacity(0.4), in: RoundedRectangle(cornerRadius: Theme.cardCornerRadius))
    }

    private func historyChart(_ series: [SeriesPoint]) -> some View {
        let dated = series.filter { $0.publishedAt != nil }
        return VStack(alignment: .leading, spacing: 8) {
            Text("Score history")
                .font(.headline)
            Chart(dated) { point in
                LineMark(
                    x: .value("Published", point.publishedAt ?? .now),
                    y: .value("Score", point.score)
                )
                .interpolationMethod(.monotone)
                PointMark(
                    x: .value("Published", point.publishedAt ?? .now),
                    y: .value("Score", point.score)
                )
                .symbolSize(24)
            }
            .foregroundStyle(Theme.scoreGradient)
            .chartYScale(domain: 0...100)
            .chartYAxis {
                AxisMarks(values: [0, 25, 50, 75, 100])
            }
            .frame(height: 180)
            .accessibilityLabel("Per-video pacing score over time")
        }
    }

    private func recentVideos(_ series: [SeriesPoint]) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Recent videos")
                .font(.headline)
            ForEach(series) { point in
                HStack {
                    VStack(alignment: .leading, spacing: 2) {
                        Text(point.title ?? point.providerVideoId)
                            .font(.subheadline)
                            .lineLimit(1)
                        HStack(spacing: 6) {
                            if let published = point.publishedAt {
                                Text(published, style: .date)
                            }
                            if let views = point.viewCount {
                                Text("\(views.formatted(.number.notation(.compactName))) views")
                            }
                        }
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    }
                    Spacer()
                    Text("\(Int(point.score.rounded()))")
                        .font(.subheadline.bold().monospacedDigit())
                        .foregroundStyle(Theme.color(forScore: point.score))
                }
                .padding(.vertical, 4)
            }
        }
    }

    // MARK: - Loading

    private func load() async {
        state = .loading
        do {
            state = .loaded(try await api.channel(id: channelID))
        } catch let error as APIClient.APIError {
            state = .failed(error.userMessage)
        } catch {
            state = .failed("Couldn't load this channel. Try again in a moment.")
        }
    }
}
