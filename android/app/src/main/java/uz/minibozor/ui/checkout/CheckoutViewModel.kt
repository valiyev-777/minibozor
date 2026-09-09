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
import uz.minibozor.data.remote.dto.CheckoutPreviewDto
import uz.minibozor.data.remote.dto.CheckoutRequest
import uz.minibozor.data.remote.dto.PickupPointDto
import uz.minibozor.data.remote.dto.SlotDayDto
import uz.minibozor.data.remote.dto.SlotDto
import uz.minibozor.data.repository.CartRepository
import uz.minibozor.data.repository.OrderRepository
import javax.inject.Inject

/**
 * Courier or counter.
 *
 * It was never a choice the customer made — it was inferred from which of
 * `addressId` and `pickupPointId` happened to be set, which meant the screen
 * could show a delivery time slot for an order being collected in person, and
 * nothing on it ever said which of the two was happening.
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
 * ``Payment`` went with the card vault. There is nothing to ask for: the
 * customer pays by card at the door or in cash at the door, and both of those
 * are complete the moment the tile is tapped. A step that is never missing is
 * a button that says "next" and does nothing.
 */
enum class CheckoutStep { Address, Time }

data class CheckoutState(
    val loading: Boolean = true,
    val error: String? = null,
    val preview: CheckoutPreviewDto? = null,
    val addresses: List<AddressDto> = emptyList(),
    val pickupPoints: List<PickupPointDto> = emptyList(),
    val slotDays: List<SlotDayDto> = emptyList(),
    val addressId: Int? = null,
    val pickupPointId: Int? = null,
    val slotId: Int? = null,
    val paymentMethod: String = "card",
    val delivery: DeliveryMethod = DeliveryMethod.Courier,
    val promoCode: String? = null,
    val placing: Boolean = false,
    val placedOrderId: Int? = null,
) {
    val selectedSlot: SlotDto?
        get() = slotDays.flatMap { it.slots }.firstOrNull { it.id == slotId }

    val selectedAddress: AddressDto?
        get() = addresses.firstOrNull { it.id == addressId }

    val selectedPickup: PickupPointDto?
        get() = pickupPoints.firstOrNull { it.id == pickupPointId }

    /** In order, so the first of them is the one to ask for next. */
    val missing: List<CheckoutStep>
        get() = buildList {
            when (delivery) {
                DeliveryMethod.Courier -> {
                    if (addressId == null) add(CheckoutStep.Address)
                    if (slotId == null) add(CheckoutStep.Time)
                }
                // Nothing to schedule when the customer is coming to fetch it.
                DeliveryMethod.Pickup -> if (pickupPointId == null) add(CheckoutStep.Address)
            }
        }

    /** What the button asks for. Null once there is nothing left to ask. */
    val nextStep: CheckoutStep? get() = missing.firstOrNull()

    val ready: Boolean get() = missing.isEmpty()
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
            val slotDays = (orders.slots(3) as? Outcome.Success)?.data.orEmpty()
            val pickups = (orders.pickupPoints() as? Outcome.Success)?.data.orEmpty()

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
                    slotDays = slotDays,
                    pickupPoints = pickups,
                    addressId = it.addressId ?: addresses.firstOrNull { a -> a.isDefault }?.id
                        ?: addresses.firstOrNull()?.id,
                    slotId = it.slotId ?: slotDays.flatMap { d -> d.slots }
                        .firstOrNull { s -> s.available }?.id,
                )
            }
            refreshPreview()
        }
    }

    /**
     * Courier or counter, as a choice rather than a side effect.
     *
     * Switching drops what belonged to the other one: an address means nothing
     * to a pickup order, and a delivery slot means nothing to either the
     * counter or an order with nowhere to go yet.
     */
    fun selectDelivery(method: DeliveryMethod) {
        if (_state.value.delivery == method) return
        _state.update {
            when (method) {
                DeliveryMethod.Courier -> it.copy(delivery = method, pickupPointId = null)
                DeliveryMethod.Pickup ->
                    it.copy(delivery = method, addressId = null, slotId = null)
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
                slotId = null,
            )
        }
        refreshPreview()
    }

    fun selectSlot(id: Int) {
        _state.update { it.copy(slotId = id) }
        refreshPreview()
    }

    /**
     * How the money changes hands, and that is the whole of the question.
     *
     * By card at the door or in cash at the door. There is no card to pick and
     * none to add: nothing here stores a PAN, and the customer taps the card
     * machine when the courier arrives.
     */
    fun selectCard() {
        _state.update { it.copy(paymentMethod = "card") }
        refreshPreview()
    }

    fun selectCash() {
        _state.update { it.copy(paymentMethod = "cash") }
        refreshPreview()
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
        slotId = slotId,
        paymentMethod = paymentMethod,
        promoCode = promoCode,
    )
}
