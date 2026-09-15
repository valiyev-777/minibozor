import Foundation
import Observation

/// Shared by screens 19–24: the five steps edit one draft order rather than
/// passing arguments between destinations.
@Observable
final class CheckoutModel {
    var loading = true
    var errorMessage: String?
    var preview: CheckoutPreviewDTO?

    var addresses: [AddressDTO] = []
    var pickupPoints: [PickupPointDTO] = []
    var cards: [CardDTO] = []

    var addressId: Int?
    var pickupPointId: Int?
    var cardId: Int?
    var paymentMethod = "card"
    var promoCode: String?

    var placing = false
    var placedOrderId: Int?

    private let orders = OrderRepository()
    private let cart = CartRepository.shared

    /// Somewhere for it to go and something to pay with. There is no window to
    /// book any more, so an order with an address on it is one the courier can
    /// take.
    var ready: Bool {
        (addressId != nil || pickupPointId != nil)
            && (paymentMethod == "cash" || cardId != nil)
    }

    @MainActor
    func load() async {
        loading = true
        errorMessage = nil

        async let addressList = orders.addresses()
        async let cardList = orders.cards()
        async let pickupList = orders.pickupPoints()

        addresses = (await addressList).value ?? []
        cards = (await cardList).value ?? []
        pickupPoints = (await pickupList).value ?? []

        if addressId == nil {
            addressId = addresses.first(where: \.isDefault)?.id ?? addresses.first?.id
        }
        if cardId == nil {
            cardId = cards.first { $0.isDefault && !$0.isExpired }?.id
                ?? cards.first { !$0.isExpired }?.id
        }
        await refreshPreview()
    }

    /// Called when returning from "add card", so a new card shows up at once.
    @MainActor
    func reloadCards() async {
        cards = (await orders.cards()).value ?? []
        if !cards.contains(where: { $0.id == cardId }) {
            cardId = cards.first { $0.isDefault && !$0.isExpired }?.id
                ?? cards.first { !$0.isExpired }?.id
        }
        await refreshPreview()
    }

    @MainActor func selectAddress(_ id: Int) async {
        addressId = id
        pickupPointId = nil
        await refreshPreview()
    }

    @MainActor func selectPickup(_ id: Int) async {
        pickupPointId = id
        addressId = nil
        await refreshPreview()
    }

    @MainActor func selectCard(_ id: Int) async {
        cardId = id
        paymentMethod = "card"
        await refreshPreview()
    }

    @MainActor func selectCash() async {
        paymentMethod = "cash"
        cardId = nil
        await refreshPreview()
    }

    @MainActor
    func createAddress(_ body: AddressRequest) async -> Bool {
        switch await orders.createAddress(body) {
        case .success(let address):
            addresses.append(address)
            addressId = address.id
            pickupPointId = nil
            await refreshPreview()
            return true
        case .failure(let message):
            errorMessage = message
            return false
        }
    }

    @MainActor
    func place() async {
        guard ready, !placing else { return }
        placing = true
        errorMessage = nil

        switch await orders.place(request) {
        case .success(let order):
            cart.clearLocally()
            _ = await cart.refresh()
            placedOrderId = order.id
        case .failure(let message):
            errorMessage = message
        }
        placing = false
    }

    /// Starts a fresh draft when the user re-enters checkout.
    @MainActor
    func reset() {
        placedOrderId = nil
        errorMessage = nil
        promoCode = nil
    }

    @MainActor
    private func refreshPreview() async {
        switch await orders.preview(request) {
        case .success(let value):
            preview = value
            errorMessage = nil
        case .failure(let message):
            errorMessage = message
        }
        loading = false
    }

    private var request: CheckoutRequest {
        CheckoutRequest(
            addressId: addressId,
            pickupPointId: pickupPointId,
            paymentMethod: paymentMethod,
            paymentCardId: cardId,
            promoCode: promoCode
        )
    }
}
