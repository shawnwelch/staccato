// Models.swift
// ASL
//
// Wire types for the ASL backend public API (v1). Shapes mirror
// asl-frontend/lib/api.ts, which is the de-facto contract for the public
// endpoints. Snake_case → camelCase is handled by the decoder configured in
// APIClient (never per-model CodingKeys), so field names here must be exact
// camelCase transliterations of the wire names.

import Foundation
import PacingKit

// MARK: - Analyses

enum AnalysisStatus: String, Codable, Sendable {
    case queued, running, complete, failed
}

enum AnalysisSource: String, Codable, Sendable {
    case url, upload, optical
}

struct Analysis: Codable, Sendable, Identifiable, Equatable {
    let id: String
    let status: AnalysisStatus
    let engineVersion: String
    let score: Double?
    let label: PacingLabel?
    let medianShotS: Double?
    let cutsPerMinute: Double?
    let cutCount: Int?
    let durationS: Double?
    let heatmapPngUrl: URL?
    let resultJsonUrl: URL?
    let source: AnalysisSource
    /// Slug of the public share page (https://{frontend}/s/{slug}). Present
    /// once the analysis completes.
    let shareSlug: String?
    let createdAt: Date
    let completedAt: Date?

    var isTerminal: Bool { status == .complete || status == .failed }
}

/// 202 body from POST /v1/analyses.
struct AnalysisCreation: Codable, Sendable {
    let id: String
    let status: AnalysisStatus
    /// Free-tier scans left AFTER this one, when the server includes it in
    /// the body. The X-Scans-Remaining header is the fallback; APIClient
    /// merges both. nil for subscribers (unlimited).
    let scansRemaining: Int?
}

struct CreateAnalysisRequest: Codable, Sendable {
    let url: String
}

// MARK: - Live sessions

/// POST /v1/live-sessions. The server recomputes the score from cutTimesS —
/// deviceScore exists only for drift telemetry, never as the stored value.
struct LiveSessionSubmission: Codable, Sendable {
    let cutTimesS: [Double]
    let durationS: Double
    let deviceScore: Double
    let contentLabel: String
}

struct LiveSessionReceipt: Codable, Sendable, Equatable {
    let id: String
    /// Server-recomputed score; should match deviceScore to ~1e-9 because
    /// both sides run engine 1.0.0 over the same cut times.
    let score: Double?
    let label: PacingLabel?
}

// MARK: - Browse

enum Trend: String, Codable, Sendable {
    case speedingUp = "speeding_up"
    case stable
    case slowingDown = "slowing_down"

    /// Direction-only iconography: arrows describe the measured change,
    /// deliberately not colored green/red "good/bad".
    var systemImage: String {
        switch self {
        case .speedingUp: "arrow.up.right"
        case .stable: "arrow.right"
        case .slowingDown: "arrow.down.right"
        }
    }

    var displayName: String {
        switch self {
        case .speedingUp: "speeding up"
        case .stable: "stable"
        case .slowingDown: "slowing down"
        }
    }
}

// Hashable: used as a NavigationStack destination value.
struct LeaderboardItem: Codable, Sendable, Identifiable, Hashable {
    var id: String { channelId }
    let rank: Int
    let channelId: String
    let title: String
    let category: String?
    let subscriberCount: Int?
    let score: Double
    let trend: Trend
    let nVideos: Int
}

struct Leaderboard: Codable, Sendable {
    let items: [LeaderboardItem]
    let page: Int
    let pageSize: Int
    let total: Int
    let categories: [String]
}

struct SeriesPoint: Codable, Sendable, Identifiable, Equatable {
    var id: String { providerVideoId }
    let providerVideoId: String
    let title: String?
    let score: Double
    let viewCount: Int?
    let publishedAt: Date?
}

struct ChannelScore: Codable, Sendable, Equatable {
    let score: Double
    let trend: Trend
    let nVideos: Int
    let engineVersion: String
    let series: [SeriesPoint]
}

struct Channel: Codable, Sendable, Identifiable, Equatable {
    let id: String
    let providerChannelId: String
    let title: String
    let subscriberCount: Int?
    let category: String?
    let score: ChannelScore?
}

// MARK: - Errors

/// Error body the backend returns for non-2xx responses.
struct APIErrorBody: Codable, Sendable {
    let error: String?
    let detail: String?
    let scansRemaining: Int?
}
