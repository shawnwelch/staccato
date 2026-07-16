// ShareViewController.swift
// ShareExtension
//
// "Scan with ASL" in the system share sheet (YouTube app, Safari, …).
// Flow: pull the URL out of the extension items → write it to the shared
// app-group defaults → show a one-beat confirmation → complete.
//
// Handoff strategy: the app-group drop is the reliable channel — the main
// app consumes it the next time it becomes active (ASLApp watches
// scenePhase). Share extensions are NOT officially allowed to open their
// containing app, so there is deliberately no URL-open trick here; the
// confirmation copy tells the user to open ASL. The asl://scan deep link
// exists for surfaces (widgets, QR, push) that ARE allowed to open the app.

import UIKit
import UniformTypeIdentifiers

final class ShareViewController: UIViewController {

    /// Must match AppGroup.identifier in the app target. Duplicated by
    /// design: the extension cannot import app-target sources, and a shared
    /// framework for one string isn't worth the build complexity.
    private static let appGroupID = "group.com.staccato.asl"
    private static let pendingKey = "pendingScanURL"

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .clear

        let providers = (extensionContext?.inputItems as? [NSExtensionItem])?
            .compactMap(\.attachments)
            .flatMap { $0 } ?? []

        Task { // inherits @MainActor
            let url = await Self.extractSharedURL(from: providers)
            if let url {
                UserDefaults(suiteName: Self.appGroupID)?
                    .set(url.absoluteString, forKey: Self.pendingKey)
                showConfirmation("Saved — open ASL to scan")
            } else {
                showConfirmation("Couldn't find a link to scan")
            }
            try? await Task.sleep(for: .seconds(1.2))
            extensionContext?.completeRequest(returningItems: nil, completionHandler: nil)
        }
    }

    // MARK: - URL extraction

    /// Looks for a URL attachment first; falls back to plain text that
    /// contains a URL (the YouTube app shares "title + URL" as text on some
    /// paths).
    private static func extractSharedURL(from providers: [NSItemProvider]) async -> URL? {
        if let urlProvider = providers.first(where: {
            $0.hasItemConformingToTypeIdentifier(UTType.url.identifier)
        }) {
            let item = try? await urlProvider.loadItem(forTypeIdentifier: UTType.url.identifier)
            if let url = item as? URL { return url }
        }

        if let textProvider = providers.first(where: {
            $0.hasItemConformingToTypeIdentifier(UTType.plainText.identifier)
        }) {
            let item = try? await textProvider.loadItem(forTypeIdentifier: UTType.plainText.identifier)
            if let text = item as? String { return firstURL(in: text) }
        }

        return nil
    }

    private static func firstURL(in text: String) -> URL? {
        let detector = try? NSDataDetector(types: NSTextCheckingResult.CheckingType.link.rawValue)
        let range = NSRange(text.startIndex..., in: text)
        return detector?.firstMatch(in: text, options: [], range: range)?.url
    }

    // MARK: - Minimal confirmation UI

    private func showConfirmation(_ message: String) {
        let container = UIVisualEffectView(effect: UIBlurEffect(style: .systemMaterial))
        container.layer.cornerRadius = 14
        container.clipsToBounds = true
        container.translatesAutoresizingMaskIntoConstraints = false

        let label = UILabel()
        label.text = message
        label.font = .preferredFont(forTextStyle: .subheadline)
        label.textAlignment = .center
        label.numberOfLines = 0
        label.translatesAutoresizingMaskIntoConstraints = false

        container.contentView.addSubview(label)
        view.addSubview(container)

        NSLayoutConstraint.activate([
            container.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            container.centerYAnchor.constraint(equalTo: view.centerYAnchor),
            container.widthAnchor.constraint(lessThanOrEqualTo: view.widthAnchor, constant: -48),
            label.topAnchor.constraint(equalTo: container.contentView.topAnchor, constant: 16),
            label.bottomAnchor.constraint(equalTo: container.contentView.bottomAnchor, constant: -16),
            label.leadingAnchor.constraint(equalTo: container.contentView.leadingAnchor, constant: 20),
            label.trailingAnchor.constraint(equalTo: container.contentView.trailingAnchor, constant: -20),
        ])
    }
}
