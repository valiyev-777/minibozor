import Foundation
import Observation

/// Screens 17–18, plus the badge on the tab bar.
///
/// Every mutation returns the whole cart, so this is the single source of truth
/// that the cart screen and the tab bar both observe.
@Observable
final class CartRepository {
    static let shared = CartRepository()

    private(set) var cart: CartDTO?

    var badgeCount: Int { cart?.totals.itemsCount ?? 0 }

    private let api = APIClient.shared

    private init() {}

    @discardableResult
    func refresh(promoCode: String? = nil) async -> Outcome<CartDTO> {
        let items = promoCode.map { [URLQueryItem(name: "promo_code", value: $0)] } ?? []
        return await store { try await api.get("cart", query: items) }
    }

    /// The triple the server folds a repeat add into.
    private struct CartLine: Hashable {
        let productId: Int
        let variantId: Int?
        let colorVariantId: Int?
    }

    /// Lines currently being added, so a second tap on one of them is dropped.
    ///
    /// The guard lives here rather than in each screen because there are five
    /// ways to add the same line — the tile in the grid, the tile in a rail,
    /// search results, the product page and the picker sheet — and only the
    /// product page had a flag of its own. Everywhere else a finger resting a
    /// moment too long put the thing in the basket twice, and the server, which
    /// folds a repeat add into the existing line by raising its quantity, could
    /// not tell the difference between two taps and a customer wanting two.
    ///
    /// Keyed on the line rather than held as one lock: adding a shirt should
    /// not be blocked because a kettle is still in flight.
    private var adding: Set<CartLine> = []

    @discardableResult
    @MainActor
    func add(
        productId: Int,
        variantId: Int? = nil,
        colorVariantId: Int? = nil,
        quantity: Int = 1
    ) async -> Outcome<CartDTO> {
        let line = CartLine(
            productId: productId,
            variantId: variantId,
            colorVariantId: colorVariantId
        )
        // On the main actor, so the check and the claim cannot interleave.
        guard adding.insert(line).inserted else {
            // A dropped tap is not an error to report — the line is on its way
            // in, which is exactly what the tap asked for. The caller gets the
            // cart it last saw and shows the same "added" it would have shown.
            return cart.map { .success($0) } ?? .failure(L("savatga_qoshildi"))
        }
        defer { adding.remove(line) }
        return await store {
            try await api.post(
                "cart/items",
                body: CartAddRequest(
                    productId: productId,
                    variantId: variantId,
                    colorVariantId: colorVariantId,
                    quantity: quantity
                )
            )
        }
    }

    @discardableResult
    func setQuantity(itemId: Int, quantity: Int) async -> Outcome<CartDTO> {
        await store {
            try await api.patch("cart/items/\(itemId)", body: CartUpdateRequest(quantity: quantity))
        }
    }

    @discardableResult
    func setSelected(itemId: Int, selected: Bool) async -> Outcome<CartDTO> {
        await store {
            try await api.patch("cart/items/\(itemId)", body: CartUpdateRequest(selected: selected))
        }
    }

    @discardableResult
    func remove(itemId: Int) async -> Outcome<CartDTO> {
        await store { try await api.delete("cart/items/\(itemId)") }
    }

    @discardableResult
    func applyPromo(_ code: String) async -> Outcome<CartDTO> {
        await store { try await api.post("cart/promo", body: PromoRequest(code: code)) }
    }

    func clearLocally() {
        cart = nil
    }

    private func store(_ block: () async throws -> CartDTO) async -> Outcome<CartDTO> {
        let outcome = await run(block)
        if case .success(let value) = outcome { cart = value }
        return outcome
    }
}
