// AppConfig.swift
// ASL
//
// Build-time configuration read from Info.plist. The values are injected by
// XcodeGen (see project.yml → targets.ASL.info.properties), so switching
// environments is a project.yml edit, not a code edit.

import Foundation

enum AppConfig {
    /// Backend base URL, e.g. https://api.staccato.example
    /// Info.plist key: ASLAPIBaseURL
    static var apiBaseURL: URL {
        guard
            let string = Bundle.main.object(forInfoDictionaryKey: "ASLAPIBaseURL") as? String,
            let url = URL(string: string)
        else {
            // Deliberate hard failure: a build without a backend URL is
            // misconfigured, and silently pointing at localhost would make
            // quota / paywall behavior look broken in confusing ways.
            fatalError("ASLAPIBaseURL missing or invalid in Info.plist — check project.yml")
        }
        return url
    }

    /// Public share-page host, e.g. staccato.example → https://staccato.example/s/{slug}
    /// Info.plist key: ASLFrontendHost
    static var frontendHost: String {
        guard let host = Bundle.main.object(forInfoDictionaryKey: "ASLFrontendHost") as? String else {
            fatalError("ASLFrontendHost missing in Info.plist — check project.yml")
        }
        return host
    }

    /// Share-page URL for a completed analysis.
    static func shareURL(slug: String) -> URL? {
        var components = URLComponents()
        components.scheme = "https"
        components.host = frontendHost
        components.path = "/s/\(slug)"
        return components.url
    }

    /// Public methodology page (linked from Settings).
    static var methodologyURL: URL? {
        var components = URLComponents()
        components.scheme = "https"
        components.host = frontendHost
        components.path = "/methodology"
        return components.url
    }
}
