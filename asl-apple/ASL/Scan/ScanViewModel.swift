// ScanViewModel.swift
// ASL
//
// State machine for the URL-scan flow:
//   idle → submitting → polling → complete | failed
// A 402 anywhere routes to the paywall WITHOUT entering `failed` — quota
// exhaustion is a product state, not an error, and must never dead-end
// (Browse stays reachable; the paywall sheet is dismissible).

import Foundation
import Observation

@MainActor
@Observable
final class ScanViewModel {

    enum Phase: Equatable {
        case idle
        case submitting
        case polling(analysisID: String)
        case complete(Analysis)
        case failed(message: String)
    }

    var urlText = ""
    private(set) var phase: Phase = .idle
    /// Server-reported free scans remaining. nil = unknown or unlimited.
    /// Displayed verbatim; never decremented client-side.
    private(set) var scansRemaining: Int?
    var showPaywall = false

    private var scanTask: Task<Void, Never>?

    var isBusy: Bool {
        switch phase {
        case .submitting, .polling: true
        default: false
        }
    }

    var canSubmit: Bool {
        !isBusy && !urlText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }

    // MARK: - Intents

    /// Prefill from a deep link / share-extension handoff.
    func adopt(pendingURL: URL) {
        guard !isBusy else { return }
        urlText = pendingURL.absoluteString
        phase = .idle
    }

    func submit(using api: APIClient) {
        guard canSubmit else { return }
        let urlString = urlText.trimmingCharacters(in: .whitespacesAndNewlines)
        scanTask?.cancel()
        scanTask = Task { await self.run(urlString: urlString, api: api) }
    }

    func reset() {
        scanTask?.cancel()
        scanTask = nil
        phase = .idle
    }

    /// Refresh the quota display from the client's last-seen server value.
    func syncQuota(from api: APIClient) async {
        scansRemaining = await api.scansRemaining
    }

    // MARK: - Flow

    private func run(urlString: String, api: APIClient) async {
        phase = .submitting
        do {
            let creation = try await api.createAnalysis(url: urlString)
            await syncQuota(from: api)
            phase = .polling(analysisID: creation.id)

            let analysis = try await api.awaitAnalysisCompletion(id: creation.id)
            guard !Task.isCancelled else { return }
            switch analysis.status {
            case .complete:
                phase = .complete(analysis)
            case .failed:
                phase = .failed(message: "This video couldn't be analyzed. Some links are private, region-locked, or unsupported.")
            case .queued, .running:
                // awaitAnalysisCompletion only returns terminal states.
                phase = .failed(message: "Unexpected response from the server.")
            }
        } catch let error as APIClient.APIError {
            guard !Task.isCancelled else { return }
            if case .quotaExhausted(let remaining) = error {
                scansRemaining = remaining
                showPaywall = true
                phase = .idle // quota is not a failure; keep the form usable
            } else {
                phase = .failed(message: error.userMessage)
            }
        } catch is CancellationError {
            // reset() or a superseding scan; state already handled.
        } catch {
            guard !Task.isCancelled else { return }
            phase = .failed(message: "Something went wrong. Try again in a moment.")
        }
    }
}
