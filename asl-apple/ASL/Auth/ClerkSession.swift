// ClerkSession.swift
// ASL
//
// Thin app-side wrapper around auth. The Clerk iOS SDK is NOT yet a
// dependency — every place it plugs in is marked TODO(clerk) and gated behind
// small protocols, so nothing in the app talks to Clerk types directly and
// the SDK can be dropped in without touching call sites.
//
// Xcode-side setup when wiring Clerk:
//   1. Add the Clerk iOS SDK package to project.yml / the project.
//   2. Configure the publishable key at app launch.
//   3. Replace the TODO(clerk) bodies below with real SDK calls.

import Foundation
import Observation

/// User-visible profile facts. Kept SDK-agnostic.
struct UserProfile: Sendable, Equatable {
    let userID: String
    let email: String?
    let displayName: String?
}

/// Everything the app needs from an auth backend. ClerkSession is the
/// production conformer; previews/tests can substitute their own.
protocol AuthSessionProviding: AuthTokenProviding {
    @MainActor var profile: UserProfile? { get }
    @MainActor func signIn() async
    @MainActor func signOut() async
}

@MainActor
@Observable
final class ClerkSession: AuthSessionProviding {

    enum State: Equatable {
        case signedOut
        case signedIn(UserProfile)
    }

    private(set) var state: State = .signedOut
    private(set) var lastErrorMessage: String?

    var profile: UserProfile? {
        if case .signedIn(let profile) = state { return profile }
        return nil
    }

    var isSignedIn: Bool { profile != nil }

    init() {
        // TODO(clerk): Clerk SDK bootstrap — configure with the publishable
        // key and restore any persisted session, then reflect it into `state`.
    }

    // MARK: - AuthSessionProviding

    func signIn() async {
        // TODO(clerk): present Clerk's sign-in UI (or a custom flow backed by
        // the SDK) and, on success:
        //   state = .signedIn(UserProfile(userID: ..., email: ..., displayName: ...))
        lastErrorMessage = "Sign-in isn't wired up in this build yet."
    }

    func signOut() async {
        // TODO(clerk): call the SDK's sign-out, then:
        state = .signedOut
    }

    // MARK: - AuthTokenProviding

    /// Bearer token for API calls. APIClient calls this per-request so token
    /// refresh stays the SDK's problem, not ours.
    nonisolated func currentToken() async throws -> String? {
        // TODO(clerk): return the current session JWT from the SDK (its
        // getToken() equivalent — the SDK caches/refreshes internally).
        // Returning nil = signed out; APIClient maps that to .unauthenticated
        // for endpoints that need auth.
        nil
    }
}
