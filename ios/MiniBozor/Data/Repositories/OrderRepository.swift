import Foundation

/// Screens 19–29, 32–33.
struct OrderRepository {
    private let api = APIClient.shared

    // Addresses

    func addresses() async -> Outcome<[AddressDTO]> {
        await run { try await api.get("addresses") }
    }

    func createAddress(_ body: AddressRequest) async -> Outcome<AddressDTO> {
        await run { try await api.post("addresses", body: body) }
    }

    func updateAddress(id: Int, body: AddressRequest) async -> Outcome<AddressDTO> {
        await run { try await api.put("addresses/\(id)", body: body) }
    }

    func deleteAddress(id: Int) async -> Outcome<Void> {
        await run { let _: MessageDTO = try await api.delete("addresses/\(id)") }
    }

    // Delivery

    func slots(days: Int = 3) async -> Outcome<[SlotDayDTO]> {
        await run {
            try await api.get("delivery/slots", query: [URLQueryItem(name: "days", value: String(days))])
        }
    }

    func pickupPoints() async -> Outcome<[PickupPointDTO]> {
        await run { try await api.get("delivery/pickup-points") }
    }

    // Cards

    func cards() async -> Outcome<[CardDTO]> {
        await run { try await api.get("payment-cards") }
    }

    func addCard(_ body: CardRequest) async -> Outcome<CardDTO> {
        await run { try await api.post("payment-cards", body: body) }
    }

    func makeCardDefault(id: Int) async -> Outcome<CardDTO> {
        await run { try await api.post("payment-cards/\(id)/default") }
    }

    func deleteCard(id: Int) async -> Outcome<Void> {
        await run { let _: MessageDTO = try await api.delete("payment-cards/\(id)") }
    }

    // Checkout and orders

    func preview(_ body: CheckoutRequest) async -> Outcome<CheckoutPreviewDTO> {
        await run { try await api.post("checkout/preview", body: body) }
    }

    func place(_ body: CheckoutRequest) async -> Outcome<OrderDTO> {
        await run { try await api.post("orders", body: body) }
    }

    func orders(active: Bool?, page: Int = 1) async -> Outcome<PageDTO<OrderSummaryDTO>> {
        var items = [URLQueryItem(name: "page", value: String(page))]
        if let active { items.append(URLQueryItem(name: "active", value: active ? "true" : "false")) }
        return await run { try await api.get("orders", query: items) }
    }

    func order(id: Int) async -> Outcome<OrderDTO> {
        await run { try await api.get("orders/\(id)") }
    }

    func cancel(id: Int, body: CancelRequest) async -> Outcome<OrderDTO> {
        await run { try await api.post("orders/\(id)/cancel", body: body) }
    }

    func requestReturn(id: Int, body: ReturnRequestBody) async -> Outcome<ReturnDTO> {
        await run { try await api.post("orders/\(id)/return", body: body) }
    }

    func returns() async -> Outcome<[ReturnDTO]> {
        await run { try await api.get("returns") }
    }

    func cancelReasons() async -> Outcome<[ReasonDTO]> {
        await run { try await api.get("orders/reasons/cancel") }
    }

    func returnReasons() async -> Outcome<[ReasonDTO]> {
        await run { try await api.get("orders/reasons/return") }
    }
}
