package uz.minibozor.ui.checkout

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import uz.minibozor.core.util.Outcome
import uz.minibozor.data.remote.dto.AddressDto
import uz.minibozor.data.remote.dto.CardDto
import uz.minibozor.data.remote.dto.AddressRequest
import uz.minibozor.data.remote.dto.CheckoutPreviewDto
import uz.minibozor.data.remote.dto.CheckoutRequest
import uz.minibozor.data.remote.dto.PickupPointDto
import uz.minibozor.data.repository.CartRepository
import uz.minibozor.data.repository.OrderRepository
import javax.inject.Inject

/**
 * Courier or counter.
 *
 * It was never a choice the customer made — it was inferred from which of
 * `addressId` and `pickupPointId` happened to be set, and nothing on the screen
 * ever said which of the two was happening.
 */
enum class DeliveryMethod { Courier, Pickup }

/**
 * What is still missing before the order can be placed.
 *
 * A list rather than a boolean: a disabled button teaches nobody what is wrong
 * with their order, and "2 qadam qoldi — manzil va to'lov" is the difference
 * between a screen that waits and a screen that asks.
 */
/**
 * What the checkout still needs before an order can be placed.
 *
 * ``Payment`` is a real step again, and it is missing in exactly one case: the
 * customer is paying by card and has not got one saved. Cash needs nothing —
 * it is settled at the door — and a card order with a card chosen needs
 * nothing either, so the step appears only when there is genuinely something
 * to go and do. A step that is never missing would be a button that says
 * "next" and does nothing; a step that is always missing would be worse.
 */
enum class CheckoutStep { Address, Payment }

data class CheckoutState(
    val loading: Boolean = true,
    val error: String? = null,
    val preview: CheckoutPreviewDto? = null,
    val addresses: List<AddressDto> = emptyList(),
    val pickupPoints: List<PickupPointDto> = emptyList(),
    val addressId: Int? = null,
    val pickupPointId: Int? = null,
    val paymentMethod: String = "card",
    val cards: List<CardDto> = emptyList(),
    val cardId: Int? = null,
    val delivery: DeliveryMethod = DeliveryMethod.Courier,
    val promoCode: String? = null,
    val placing: Boolean = false,
    val placedOrderId: Int? = null,
) {
    val selectedAddress: AddressDto?
        get() = addresses.firstOrNull { it.id == addressId }

    val selectedPickup: PickupPointDto?
        get() = pickupPoints.firstOrNull { it.id == pickupPointId }

    val selectedCard: CardDto?
        get() = cards.firstOrNull { it.id == cardId }

    /** A card that can actually be charged; an expired one cannot. */
    val usableCards: List<CardDto>
        get() = cards.filter { it.status == "active" }

    /** In order, so the first of them is the one to ask for next. */
    val missing: List<CheckoutStep>
        get() = buildList {
            // Somewhere for it to go, and that is the whole of the delivery
            // question now: there is no window to book, so an order with an
            // address on it is an order the courier can take.
            when (delivery) {
                DeliveryMethod.Courier -> if (addressId == null) add(CheckoutStep.Address)
                DeliveryMethod.Pickup -> if (pickupPointId == null) add(CheckoutStep.Address)
            }
            // Last, because it is the last thing anybody wants to be asked
            // about: where it goes comes first, and then what pays for it.
            if (paymentMethod != "cash" && cardId == null) add(CheckoutStep.Payment)
        }

    /** What the button asks for. Null once there is nothing left to ask. */
    val nextStep: CheckoutStep? get() = missing.firstOrNull()

    val ready: Boolean get() = missing.isEmpty()
}

/**
 * Shared by screens 19–24. Scoped to the checkout nav graph so the three steps
 * edit one draft order rather than passing arguments between destinations.
 */
@HiltViewModel
class CheckoutViewModel @Inject constructor(
    private val orders: OrderRepository,
    private val cart: CartRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(CheckoutState())
    val state = _state.asStateFlow()

    init {
        load()
    }

    fun load() {
        viewModelScope.launch {
            _state.update { it.copy(loading = true, error = null) }

            val addresses = (orders.addresses() as? Outcome.Success)?.data.orEmpty()
            val pickups = (orders.pickupPoints() as? Outcome.Success)?.data.orEmpty()
            val cards = (orders.cards() as? Outcome.Success)?.data.orEmpty()

            _state.update {
                it.copy(
                    addresses = addresses,
                    // The code the basket was priced with, carried into the
                    // order. It lives in the request rather than in the cart,
                    // so a discount the customer had accepted in the basket
                    // used to be dropped the moment they pressed "Buyurtma
                    // berish" — the checkout asked for a preview with no code
                    // on it and quietly charged the full amount.
                    promoCode = it.promoCode ?: cart.promoCode.value,
                    pickupPoints = pickups,
                    addressId = it.addressId ?: addresses.firstOrNull { a -> a.isDefault }?.id
                        ?: addresses.firstOrNull()?.id,
                    cards = cards,
                    // The default, or the first one that can be charged. A
                    // shopper with one saved card should not have to choose it.
                    cardId = it.cardId
                        ?: cards.firstOrNull { c -> c.isDefault && c.status == "active" }?.id
                        ?: cards.firstOrNull { c -> c.status == "active" }?.id,
                )
            }
            refreshPreview()
        }
    }

    /**
     * Courier or counter, as a choice rather than a side effect.
     *
     * Switching drops what belonged to the other one: an address means nothing
     * to a pickup order, and a counter means nothing to one being carried to
     * the door.
     */
    fun selectDelivery(method: DeliveryMethod) {
        if (_state.value.delivery == method) return
        _state.update {
            when (method) {
                DeliveryMethod.Courier -> it.copy(delivery = method, pickupPointId = null)
                DeliveryMethod.Pickup -> it.copy(delivery = method, addressId = null)
            }
        }
        refreshPreview()
    }

    fun selectAddress(id: Int) {
        _state.update {
            it.copy(delivery = DeliveryMethod.Courier, addressId = id, pickupPointId = null)
        }
        refreshPreview()
    }

    fun selectPickup(id: Int) {
        _state.update {
            it.copy(
                delivery = DeliveryMethod.Pickup,
                pickupPointId = id,
                addressId = null,
            )
        }
        refreshPreview()
    }

    /**
     * How the money changes hands.
     *
     * Online by card, charged when the order is placed, or in cash to the
     * courier at the door. Tapping "Karta" with nothing saved selects the
     * method and leaves [CheckoutStep.Payment] outstanding, which is what
     * sends the customer to the form — rather than a tile that looks chosen
     * and a button that is then refused by the server.
     */
    fun selectCard(id: Int? = null) {
        _state.update {
            it.copy(
                paymentMethod = "card",
                cardId = id ?: it.cardId
                    ?: it.cards.firstOrNull { c -> c.isDefault && c.status == "active" }?.id
                    ?: it.cards.firstOrNull { c -> c.status == "active" }?.id,
            )
        }
        refreshPreview()
    }

    fun selectCash() {
        // The card is forgotten, not remembered: a cash order that still names
        // one is a request the server refuses to read either way, and leaving
        // it set meant switching back to Karta silently re-selected a card the
        // customer may have been trying to get away from.
        _state.update { it.copy(paymentMethod = "cash", cardId = null) }
        refreshPreview()
    }

    /** Called when returning from "Karta qo'shish", so a new card shows up at once. */
    fun reloadCards() {
        viewModelScope.launch {
            val cards = (orders.cards() as? Outcome.Success)?.data.orEmpty()
            _state.update { state ->
                val stillThere = cards.any { it.id == state.cardId }
                state.copy(
                    cards = cards,
                    cardId = if (stillThere) state.cardId else {
                        cards.firstOrNull { it.isDefault && it.status == "active" }?.id
                            ?: cards.firstOrNull { it.status == "active" }?.id
                    },
                )
            }
            refreshPreview()
        }
    }

    /** Called when returning from the address form, so a new one shows up. */
    fun reloadAddresses() {
        viewModelScope.launch {
            val addresses = (orders.addresses() as? Outcome.Success)?.data.orEmpty()
            _state.update { state ->
                val stillThere = addresses.any { it.id == state.addressId }
                state.copy(
                    addresses = addresses,
                    addressId = when {
                        stillThere -> state.addressId
                        state.pickupPointId != null -> null
                        else -> addresses.firstOrNull { it.isDefault }?.id
                            ?: addresses.firstOrNull()?.id
                    },
                )
            }
            refreshPreview()
        }
    }

    fun place() {
        val current = _state.value
        if (!current.ready || current.placing) return
        _state.update { it.copy(placing = true, error = null) }
        viewModelScope.launch {
            when (val result = orders.place(current.request())) {
                is Outcome.Success -> {
                    cart.invalidate()
                    cart.refresh()
                    _state.update { it.copy(placing = false, placedOrderId = result.data.id) }
                }
                is Outcome.Failure ->
                    _state.update { it.copy(placing = false, error = result.message) }
            }
        }
    }

    private fun refreshPreview() {
        viewModelScope.launch {
            when (val result = orders.preview(_state.value.request())) {
                is Outcome.Success ->
                    _state.update { it.copy(loading = false, preview = result.data, error = null) }
                is Outcome.Failure ->
                    _state.update { it.copy(loading = false, error = result.message) }
            }
        }
    }

    private fun CheckoutState.request() = CheckoutRequest(
        addressId = addressId,
        pickupPointId = pickupPointId,
        paymentMethod = paymentMethod,
        // Only on a card order. The server refuses a cash order that names a
        // card, and rightly: a client that sends both has not decided.
        paymentCardId = cardId.takeIf { paymentMethod == "card" },
        promoCode = promoCode,
    )
}
