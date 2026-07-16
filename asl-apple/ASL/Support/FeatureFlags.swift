// FeatureFlags.swift
// ASL

import Foundation

/// Compile-time defaults with a local override hatch (UserDefaults) so QA can
/// flip flags from a debug menu without a new build. No remote-config
/// dependency yet; when one lands it slots in behind these accessors.
enum FeatureFlags {
    /// Live camera capture ships dark. Defaults to FALSE — the tab is hidden
    /// entirely until this flips, and even then it is paid-only.
    static var liveCaptureEnabled: Bool {
        // `bool(forKey:)` returns false for a missing key, which is exactly
        // the default we want.
        UserDefaults.standard.bool(forKey: Keys.liveCaptureEnabled)
    }

    enum Keys {
        static let liveCaptureEnabled = "flag.liveCaptureEnabled"
    }
}
