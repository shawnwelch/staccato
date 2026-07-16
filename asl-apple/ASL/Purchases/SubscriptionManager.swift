// SubscriptionManager.swift
// ASL
//
// StoreKit 2 wrapper for the single subscription product. Entitlement truth
// lives with StoreKit (Transaction.currentEntitlements); the server keys the
// unlimited-scan quota off its own receipt validation, so this class only
// drives client UI (paywall, Live tab gate, Settings status).

import Foundation
import Observation
import StoreKit

@MainActor
@Observable
final class SubscriptionManager {

    /// App Store Connect product id for "ASL Unlimited" ($9.99/month).
    static let monthlyProductID = "asl.monthly.999"

    enum LoadState: Equatable {
        case idle
        case loading
        case loaded
        case failed(String)
    }

    private(set) var productLoadState: LoadState = .idle
    private(set) var monthlyProduct: Product?
    private(set) var isSubscribed = false
    private(set) var isPurchasing = false
    private(set) var lastErrorMessage: String?

    /// Localized price string for UI ("$9.99/month" equivalent per storefront).
    var displayPrice: String? { monthlyProduct?.displayPrice }

    private var updatesTask: Task<Void, Never>?

    /// Call once at launch (ASLApp .task). Starts the transaction-updates
    /// listener, loads products, and reads current entitlements.
    func start() async {
        guard updatesTask == nil else { return }
        // Transaction.updates delivers renewals, Ask-to-Buy resolutions, and
        // purchases made outside the app. Listen for the app's lifetime.
        updatesTask = Task { [weak self] in
            for await update in Transaction.updates {
                await self?.handle(update: update)
            }
        }
        await loadProducts()
        await refreshEntitlements()
    }

    deinit {
        updatesTask?.cancel()
    }

    func loadProducts() async {
        productLoadState = .loading
        do {
            let products = try await Product.products(for: [Self.monthlyProductID])
            monthlyProduct = products.first
            productLoadState = products.isEmpty
                ? .failed("Subscription product not found.")
                : .loaded
        } catch {
            productLoadState = .failed(error.localizedDescription)
        }
    }

    /// Recompute `isSubscribed` from the ground truth.
    func refreshEntitlements() async {
        var active = false
        for await entitlement in Transaction.currentEntitlements {
            guard case .verified(let transaction) = entitlement else { continue }
            if transaction.productID == Self.monthlyProductID,
               transaction.revocationDate == nil {
                active = true
            }
        }
        isSubscribed = active
    }

    /// Runs the purchase flow. Returns true when the entitlement is active
    /// afterward (callers use it to dismiss the paywall).
    @discardableResult
    func purchase() async -> Bool {
        guard let product = monthlyProduct else {
            lastErrorMessage = "Subscription isn't available right now."
            return false
        }
        isPurchasing = true
        defer { isPurchasing = false }
        lastErrorMessage = nil
        do {
            let result = try await product.purchase()
            switch result {
            case .success(let verification):
                switch verification {
                case .verified(let transaction):
                    await transaction.finish()
                    await refreshEntitlements()
                case .unverified:
                    lastErrorMessage = "Purchase couldn't be verified."
                }
            case .userCancelled:
                break
            case .pending:
                // Ask to Buy / SCA — resolution arrives via Transaction.updates.
                lastErrorMessage = "Purchase is pending approval."
            @unknown default:
                break
            }
        } catch {
            lastErrorMessage = error.localizedDescription
        }
        return isSubscribed
    }

    /// "Restore purchases" — StoreKit 2 syncs entitlements from the App Store.
    func restore() async {
        do {
            try await AppStore.sync()
            await refreshEntitlements()
        } catch {
            lastErrorMessage = error.localizedDescription
        }
    }

    private func handle(update: VerificationResult<Transaction>) async {
        guard case .verified(let transaction) = update else { return }
        await transaction.finish()
        await refreshEntitlements()
    }
}
