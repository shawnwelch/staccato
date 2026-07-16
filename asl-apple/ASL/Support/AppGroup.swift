// AppGroup.swift
// ASL
//
// Handoff channel between the share extension and the app, plus the deep-link
// grammar. Both processes read/write the shared app-group defaults; the deep
// link is a best-effort accelerator on top (see ShareViewController for why).

import Foundation

enum AppGroup {
    /// Must match the App Group entitlement on BOTH the app and the share
    /// extension (project.yml generates the entitlements; the group itself is
    /// registered in the developer portal — Xcode-side setup).
    static let identifier = "group.com.staccato.asl"

    static var defaults: UserDefaults? {
        UserDefaults(suiteName: identifier)
    }
}

/// One pending "please scan this" URL dropped off by the share extension.
/// Single-slot on purpose: sharing twice before opening the app keeps only
/// the most recent URL, which matches user expectation.
struct PendingScanStore: Sendable {
    static let key = "pendingScanURL"

    private let suiteName: String

    init(suiteName: String = AppGroup.identifier) {
        self.suiteName = suiteName
    }

    private var defaults: UserDefaults? { UserDefaults(suiteName: suiteName) }

    func save(_ url: URL) {
        defaults?.set(url.absoluteString, forKey: Self.key)
    }

    /// Returns and clears the pending URL, if any.
    func consume() -> URL? {
        guard
            let defaults,
            let string = defaults.string(forKey: Self.key),
            let url = URL(string: string)
        else { return nil }
        defaults.removeObject(forKey: Self.key)
        return url
    }
}

/// Deep links the app answers (CFBundleURLSchemes: ["asl"]).
///
///   asl://scan?url=<percent-encoded video URL>   → open Scan tab, prefill URL
///   asl://scan                                   → open Scan tab
enum DeepLink: Equatable, Sendable {
    case scan(videoURL: URL?)

    static func parse(_ url: URL) -> DeepLink? {
        guard url.scheme?.lowercased() == "asl" else { return nil }
        guard url.host?.lowercased() == "scan" else { return nil }
        let components = URLComponents(url: url, resolvingAgainstBaseURL: false)
        let videoURL = components?.queryItems?
            .first { $0.name == "url" }?
            .value
            .flatMap(URL.init(string:))
        return .scan(videoURL: videoURL)
    }
}
