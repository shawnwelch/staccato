// APIClient.swift
// ASL
//
// Actor-isolated HTTP client for the ASL backend. All async/await, typed
// errors, and honest quota accounting: `scansRemaining` only ever reflects
// what the server said (header or body) — the client never estimates.

import Foundation

// MARK: - Auth seam

/// The only thing APIClient knows about auth. ClerkSession conforms; tests
/// and previews use StubTokenProvider.
protocol AuthTokenProviding: Sendable {
    /// Current bearer token (a Clerk session JWT once the SDK is wired), or
    /// nil when signed out. Throwing means "auth is broken", not "signed out".
    func currentToken() async throws -> String?
}

/// Placeholder until the Clerk iOS SDK is wired (see ClerkSession.swift).
struct StubTokenProvider: AuthTokenProviding {
    var token: String?
    func currentToken() async throws -> String? { token }
}

// MARK: - Client

actor APIClient {

    enum APIError: Error, Equatable {
        case invalidURL
        /// Server said 401/403 — sign in (again).
        case unauthenticated
        /// Server said 402: free-tier scans exhausted. `remaining` is the
        /// server-reported remaining count (0 in practice).
        case quotaExhausted(remaining: Int)
        case http(status: Int, message: String?)
        case invalidResponse
        case decoding(description: String)
        case transport(description: String)
    }

    /// Most recent server-reported free-scan count (from the
    /// X-Scans-Remaining header or a response body). nil = server hasn't
    /// said / user is unlimited. Never computed locally.
    private(set) var scansRemaining: Int?

    private let baseURL: URL
    private let tokenProvider: any AuthTokenProviding
    private let session: URLSession
    private let decoder: JSONDecoder
    private let encoder: JSONEncoder

    static let scansRemainingHeader = "X-Scans-Remaining"

    init(
        baseURL: URL,
        tokenProvider: any AuthTokenProviding,
        session: URLSession = .shared
    ) {
        self.baseURL = baseURL
        self.tokenProvider = tokenProvider
        self.session = session

        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        decoder.dateDecodingStrategy = .custom { d in
            let container = try d.singleValueContainer()
            let string = try container.decode(String.self)
            if let date = Self.parseISO8601(string) { return date }
            throw DecodingError.dataCorruptedError(
                in: container, debugDescription: "Unparseable ISO-8601 date: \(string)")
        }
        self.decoder = decoder

        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        self.encoder = encoder
    }

    // MARK: - Endpoints

    /// POST /v1/analyses — returns 202 with the new analysis id.
    /// Throws .quotaExhausted on 402 (free tier used up).
    func createAnalysis(url: String) async throws -> AnalysisCreation {
        let creation: AnalysisCreation = try await send(
            "POST", path: "/v1/analyses",
            body: CreateAnalysisRequest(url: url),
            authenticated: true
        )
        if let remaining = creation.scansRemaining {
            scansRemaining = remaining
        }
        return creation
    }

    /// GET /v1/analyses/{id}
    func analysis(id: String) async throws -> Analysis {
        try await send("GET", path: "/v1/analyses/\(id)", authenticated: true)
    }

    /// Polls GET /v1/analyses/{id} until it reaches a terminal status.
    /// Cooperatively cancellable (Task.sleep throws on cancellation).
    func awaitAnalysisCompletion(
        id: String,
        pollInterval: Duration = .seconds(2)
    ) async throws -> Analysis {
        while true {
            let analysis = try await analysis(id: id)
            if analysis.isTerminal { return analysis }
            try await Task.sleep(for: pollInterval)
        }
    }

    /// GET /v1/leaderboard — public, no auth needed.
    func leaderboard(
        category: String? = nil,
        page: Int = 1,
        pageSize: Int = 25,
        order: String = "desc"
    ) async throws -> Leaderboard {
        var query = [
            URLQueryItem(name: "page", value: String(page)),
            URLQueryItem(name: "page_size", value: String(pageSize)),
            URLQueryItem(name: "order", value: order),
        ]
        if let category {
            query.append(URLQueryItem(name: "category", value: category))
        }
        return try await send("GET", path: "/v1/leaderboard", query: query, authenticated: false)
    }

    /// GET /v1/channels/{id} — public.
    func channel(id: String) async throws -> Channel {
        try await send("GET", path: "/v1/channels/\(id)", authenticated: false)
    }

    /// POST /v1/live-sessions — paid feature; server recomputes the score.
    func submitLiveSession(_ submission: LiveSessionSubmission) async throws -> LiveSessionReceipt {
        try await send("POST", path: "/v1/live-sessions", body: submission, authenticated: true)
    }

    // MARK: - Core request machinery

    private func send<Response: Decodable>(
        _ method: String,
        path: String,
        query: [URLQueryItem] = [],
        authenticated: Bool
    ) async throws -> Response {
        try await perform(request: makeRequest(method, path: path, query: query, bodyData: nil, authenticated: authenticated))
    }

    private func send<Response: Decodable>(
        _ method: String,
        path: String,
        query: [URLQueryItem] = [],
        body: some Encodable,
        authenticated: Bool
    ) async throws -> Response {
        let data: Data
        do {
            data = try encoder.encode(body)
        } catch {
            throw APIError.decoding(description: "encode failure: \(error)")
        }
        return try await perform(request: makeRequest(method, path: path, query: query, bodyData: data, authenticated: authenticated))
    }

    private func makeRequest(
        _ method: String,
        path: String,
        query: [URLQueryItem],
        bodyData: Data?,
        authenticated: Bool
    ) async throws -> URLRequest {
        guard var components = URLComponents(
            url: baseURL.appending(path: path),
            resolvingAgainstBaseURL: false
        ) else { throw APIError.invalidURL }
        if !query.isEmpty { components.queryItems = query }
        guard let url = components.url else { throw APIError.invalidURL }

        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        if let bodyData {
            request.httpBody = bodyData
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        if authenticated {
            guard let token = try await tokenProvider.currentToken() else {
                throw APIError.unauthenticated
            }
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        return request
    }

    private func perform<Response: Decodable>(request: URLRequest) async throws -> Response {
        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await session.data(for: request)
        } catch {
            throw APIError.transport(description: error.localizedDescription)
        }
        guard let http = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }

        // Quota header can ride on ANY authenticated response — record it
        // whenever present so the UI stays honest without extra round-trips.
        if let headerValue = http.value(forHTTPHeaderField: Self.scansRemainingHeader),
           let remaining = Int(headerValue) {
            scansRemaining = remaining
        }

        switch http.statusCode {
        case 200...299:
            do {
                return try decoder.decode(Response.self, from: data)
            } catch {
                throw APIError.decoding(description: String(describing: error))
            }
        case 401, 403:
            throw APIError.unauthenticated
        case 402:
            let body = try? decoder.decode(APIErrorBody.self, from: data)
            let remaining = body?.scansRemaining ?? 0
            scansRemaining = remaining
            throw APIError.quotaExhausted(remaining: remaining)
        default:
            let body = try? decoder.decode(APIErrorBody.self, from: data)
            throw APIError.http(
                status: http.statusCode,
                message: body?.error ?? body?.detail
            )
        }
    }

    // MARK: - Dates

    /// Accepts ISO-8601 with or without fractional seconds (the backend emits
    /// both depending on the field).
    private static func parseISO8601(_ string: String) -> Date? {
        // ISO8601FormatStyle is Sendable and cheap; formatter objects would
        // need actor confinement, so parse with the value-typed style.
        if let date = try? Date.ISO8601FormatStyle(includingFractionalSeconds: true).parse(string) {
            return date
        }
        return try? Date.ISO8601FormatStyle().parse(string)
    }
}

// MARK: - User-facing error copy

extension APIClient.APIError {
    /// Short, neutral, non-technical message for inline display.
    var userMessage: String {
        switch self {
        case .invalidURL:
            "That doesn't look like a valid link."
        case .unauthenticated:
            "Please sign in to scan videos."
        case .quotaExhausted:
            "You've used all of your free scans."
        case .http(let status, let message):
            message ?? "The server returned an error (\(status)). Try again in a moment."
        case .invalidResponse, .decoding:
            "Unexpected response from the server. Try again in a moment."
        case .transport:
            "Couldn't reach the server. Check your connection and try again."
        }
    }
}
