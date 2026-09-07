package uz.minibozor.data.repository

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.getAndUpdate
import kotlinx.coroutines.flow.update
import uz.minibozor.R
import uz.minibozor.core.util.AppStrings
import uz.minibozor.core.util.Outcome
import uz.minibozor.core.util.apiCall
import uz.minibozor.data.remote.MiniBozorApi
import uz.minibozor.data.remote.dto.CartAddRequest
import uz.minibozor.data.remote.dto.CartDto
import uz.minibozor.data.remote.dto.CartUpdateRequest
import uz.minibozor.data.remote.dto.PromoRequest
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Every mutation returns the whole cart, so this repository can keep a single
 * source of truth that the tab bar badge and the cart screen both observe.
 */
@Singleton
class CartRepository @Inject constructor(private val api: MiniBozorApi) {

    private val _cart = MutableStateFlow<CartDto?>(null)
    val cart: StateFlow<CartDto?> = _cart.asStateFlow()

    val badgeCount: Int get() = _cart.value?.totals?.itemsCount ?: 0

    /**
     * The promo code the customer has had accepted, if any.
     *
     * The basket does not hold it — the server takes a code as an argument and
     * hands back a cart priced with it, so the discount lives in the request
     * and nowhere else. Anything that rebuilds the cart without passing it
     * along quietly drops the discount, which is what changing a quantity used
     * to do. So it is kept here, next to the cart it belongs to, and every read
     * and every mutation carries it.
     */
    private val _promoCode = MutableStateFlow<String?>(null)
    val promoCode: StateFlow<String?> = _promoCode.asStateFlow()

    suspend fun refresh(promoCode: String? = _promoCode.value): Outcome<CartDto> =
        apiCall { api.cart(promoCode) }.also { it.cache() }

    /**
     * Lines currently being added, so a second tap on one of them is dropped.
     *
     * The guard lives here rather than in each screen because there are five
     * ways to add the same line — the tile in the grid, the tile in a rail,
     * search results, the product page and the picker sheet — and only the
     * product page had a flag of its own. Everywhere else a finger resting a
     * moment too long put the thing in the basket twice, and the server, which
     * folds a repeat add into the existing line by raising its quantity, could
     * not tell the difference between two taps and a customer wanting two.
     *
     * Keyed on the line rather than held as one lock: adding a shirt should not
     * be blocked because a kettle is still in flight.
     */
    private val adding = MutableStateFlow<Set<CartLine>>(emptySet())

    /** The triple the server folds a repeat add into. */
    private data class CartLine(val productId: Int, val variantId: Int?, val colorVariantId: Int?)

    suspend fun add(
        productId: Int,
        variantId: Int? = null,
        colorVariantId: Int? = null,
        quantity: Int = 1,
    ): Outcome<CartDto> {
        val line = CartLine(productId, variantId, colorVariantId)
        // getAndUpdate, so the check and the claim are one step: two taps
        // landing in the same frame would both pass a read-then-write.
        val busy = adding.getAndUpdate { it + line }.contains(line)
        // A dropped tap is not an error to report — the line is on its way in,
        // which is exactly what the tap asked for. The caller gets the cart it
        // last saw and shows the same "added" it would have shown anyway.
        if (busy) return _cart.value?.let { Outcome.Success(it) }
            ?: Outcome.Failure(AppStrings[R.string.savatga_qoshildi])
        return try {
            mutate { api.addToCart(CartAddRequest(productId, variantId, colorVariantId, quantity)) }
        } finally {
            adding.update { it - line }
        }
    }

    suspend fun setQuantity(itemId: Int, quantity: Int): Outcome<CartDto> =
        mutate { api.updateCartItem(itemId, CartUpdateRequest(quantity = quantity)) }

    suspend fun setSelected(itemId: Int, selected: Boolean): Outcome<CartDto> =
        mutate { api.updateCartItem(itemId, CartUpdateRequest(selected = selected)) }

    /** Every line at once, for the "select all" row at the top of the basket. */
    suspend fun setAllSelected(selected: Boolean): Outcome<CartDto> {
        val lines = _cart.value?.items.orEmpty().filter { it.selected != selected }
        var last: Outcome<CartDto>? = null
        for (line in lines) {
            last = setSelected(line.id, selected)
            if (last is Outcome.Failure) return last
        }
        return last ?: _cart.value?.let { Outcome.Success(it) } ?: refresh()
    }

    suspend fun remove(itemId: Int): Outcome<CartDto> = mutate { api.removeCartItem(itemId) }

    suspend fun clear(): Outcome<CartDto> {
        _promoCode.value = null
        return apiCall { api.clearCart() }.also { it.cache() }
    }

    suspend fun applyPromo(code: String): Outcome<CartDto> =
        apiCall { api.applyPromo(PromoRequest(code)) }
            .also { if (it is Outcome.Success) _promoCode.value = code.uppercase() }
            .also { it.cache() }

    /** Takes the code back off, and re-prices the basket without it. */
    suspend fun clearPromo(): Outcome<CartDto> {
        _promoCode.value = null
        return refresh(null)
    }

    /**
     * A change to a line, followed by a re-read if a promo code is in play.
     *
     * The mutating endpoints all hand back the whole cart, which is why this
     * repository can be the single source of truth — but they build it without
     * a promo code, because the code is not something the basket stores. One
     * extra read is the price of a discount that does not vanish the moment
     * somebody presses plus.
     */
    private suspend fun mutate(call: suspend () -> CartDto): Outcome<CartDto> {
        val result = apiCall { call() }
        result.cache()
        return if (result is Outcome.Success && _promoCode.value != null) refresh() else result
    }

    fun invalidate() {
        _cart.value = null
        _promoCode.value = null
    }

    private fun Outcome<CartDto>.cache() {
        if (this is Outcome.Success) _cart.value = data
    }
}
