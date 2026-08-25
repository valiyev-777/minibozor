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
import uz.minibozor.data.remote.dto.AddressRequest
import uz.minibozor.data.remote.dto.CardDto
import uz.minibozor.data.remote.dto.CheckoutPreviewDto
import uz.minibozor.data.remote.dto.CheckoutRequest
import uz.minibozor.data.remote.dto.PickupPointDto
import uz.minibozor.data.remote.dto.SlotDayDto
import uz.minibozor.data.remote.dto.SlotDto
import uz.minibozor.data.repository.CartRepository
import uz.minibozor.data.repository.OrderRepository
import javax.inject.Inject

data class CheckoutState(
    val loading: Boolean = true,
    val error: String? = null,
    val preview: CheckoutPreviewDto? = null,
    val addresses: List<AddressDto> = emptyList(),
    val pickupPoints: List<PickupPointDto> = emptyList(),
    val slotDays: List<SlotDayDto> = emptyList(),
    val cards: List<CardDto> = emptyList(),
    val addressId: Int? = null,
    val pickupPointId: Int? = null,
    val slotId: Int? = null,
    val cardId: Int? = null,
    val paymentMethod: String = "card",
    val promoCode: String? = null,
    val placing: Boolean = false,
    val placedOrderId: Int? = null,
) {
    val selectedSlot: SlotDto?
        get() = slotDays.flatMap { it.slots }.firstOrNull { it.id == slotId }

    val selectedAddress: AddressDto?
        get() = addresses.firstOrNull { it.id == addressId }

    val selectedCard: CardDto?
        get() = cards.firstOrNull { it.id == cardId }

    val ready: Boolean
        get() = (addressId != null || pickupPointId != null) &&
            (pickupPointId != null || slotId != null) &&
            (paymentMethod == "cash" || cardId != null)
}

/**
 * Shared by screens 19–24. Scoped to the checkout nav graph so the four steps
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
            val cards = (orders.cards() as? Outcome.Success)?.data.orEmpty()
            val slotDays = (orders.slots(3) as? Outcome.Success)?.data.orEmpty()
            val pickups = (orders.pickupPoints() as? Outcome.Success)?.data.orEmpty()

            _state.update {
                it.copy(
                    addresses = addresses,
                    cards = cards,
                    slotDays = slotDays,
                    pickupPoints = pickups,
                    addressId = it.addressId ?: addresses.firstOrNull { a -> a.isDefault }?.id
                        ?: addresses.firstOrNull()?.id,
                    cardId = it.cardId ?: cards.firstOrNull { c -> c.isDefault && c.status == "active" }?.id
                        ?: cards.firstOrNull { c -> c.status == "active" }?.id,
                    slotId = it.slotId ?: slotDays.flatMap { d -> d.slots }
                        .firstOrNull { s -> s.available }?.id,
                )
            }
            refreshPreview()
        }
    }

    fun selectAddress(id: Int) {
        _state.update { it.copy(addressId = id, pickupPointId = null) }
        refreshPreview()
    }

    fun selectPickup(id: Int) {
        _state.update { it.copy(pickupPointId = id, addressId = null, slotId = null) }
        refreshPreview()
    }

    fun selectSlot(id: Int) {
        _state.update { it.copy(slotId = id) }
        refreshPreview()
    }

    fun selectCard(id: Int) {
        _state.update { it.copy(cardId = id, paymentMethod = "card") }
        refreshPreview()
    }

    fun selectCash() {
        _state.update { it.copy(paymentMethod = "cash", cardId = null) }
        refreshPreview()
    }

    fun createAddress(body: AddressRequest, onDone: () -> Unit) {
        viewModelScope.launch {
            when (val result = orders.createAddress(body)) {
                is Outcome.Success -> {
                    _state.update {
                        it.copy(
                            addresses = it.addresses + result.data,
                            addressId = result.data.id,
                            pickupPointId = null,
                        )
                    }
                    refreshPreview()
                    onDone()
                }
                is Outcome.Failure -> _state.update { it.copy(error = result.message) }
            }
        }
    }

    /** Called when returning from "add card", so a new card shows up at once. */
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
        slotId = slotId,
        paymentMethod = paymentMethod,
        paymentCardId = cardId,
        promoCode = promoCode,
    )
}
