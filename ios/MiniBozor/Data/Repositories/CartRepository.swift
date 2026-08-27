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

    @discardableResult
    func add(
        productId: Int,
        variantId: Int? = nil,
        colorVariantId: Int? = nil,
        quantity: Int = 1
    ) async -> Outcome<CartDTO> {
        await store {
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
