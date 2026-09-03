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

    suspend fun refresh(promoCode: String? = null): Outcome<CartDto> =
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
            apiCall {
                api.addToCart(CartAddRequest(productId, variantId, colorVariantId, quantity))
            }.also { it.cache() }
        } finally {
            adding.update { it - line }
        }
    }

    suspend fun setQuantity(itemId: Int, quantity: Int): Outcome<CartDto> =
        apiCall { api.updateCartItem(itemId, CartUpdateRequest(quantity = quantity)) }
            .also { it.cache() }

    suspend fun setSelected(itemId: Int, selected: Boolean): Outcome<CartDto> =
        apiCall { api.updateCartItem(itemId, CartUpdateRequest(selected = selected)) }
            .also { it.cache() }

    suspend fun remove(itemId: Int): Outcome<CartDto> =
        apiCall { api.removeCartItem(itemId) }.also { it.cache() }

    suspend fun clear(): Outcome<CartDto> = apiCall { api.clearCart() }.also { it.cache() }

    suspend fun applyPromo(code: String): Outcome<CartDto> =
        apiCall { api.applyPromo(PromoRequest(code)) }.also { it.cache() }

    fun invalidate() {
        _cart.value = null
    }

    private fun Outcome<CartDto>.cache() {
        if (this is Outcome.Success) _cart.value = data
    }
}
