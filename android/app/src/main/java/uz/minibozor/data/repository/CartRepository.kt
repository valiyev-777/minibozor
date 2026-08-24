package uz.minibozor.data.repository

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
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

    suspend fun add(productId: Int, variantId: Int?, quantity: Int = 1): Outcome<CartDto> =
        apiCall { api.addToCart(CartAddRequest(productId, variantId, quantity)) }.also { it.cache() }

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
