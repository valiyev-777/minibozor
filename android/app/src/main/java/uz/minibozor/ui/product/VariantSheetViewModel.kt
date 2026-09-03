package uz.minibozor.ui.product

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import uz.minibozor.core.util.Outcome
import uz.minibozor.data.remote.dto.ProductDto
import uz.minibozor.data.remote.dto.VariantDto
import uz.minibozor.data.repository.CartRepository
import uz.minibozor.data.repository.CatalogRepository
import javax.inject.Inject

data class VariantSheetState(
    val loading: Boolean = true,
    val product: ProductDto? = null,
    val sizeId: Int? = null,
    val colorId: Int? = null,
    val quantity: Int = 1,
    /** Set once the line is in the cart; the bottom bar becomes a stepper. */
    val cartItemId: Int? = null,
    val busy: Boolean = false,
    val error: String? = null,
) {
    val colors: List<VariantDto> get() = product?.variants.orEmpty().filter { it.kind == "color" }
    val sizes: List<VariantDto> get() = product?.variants.orEmpty().filter { it.kind == "size" }

    val selectedColor: VariantDto? get() = colors.firstOrNull { it.id == colorId }
    val selectedSize: VariantDto? get() = sizes.firstOrNull { it.id == sizeId }

    /**
     * How many of the thing actually chosen are left: the colour's share of the
     * shelf, or the whole shelf when the colours are not counted apart. The
     * sheet is adding one colour, so that is the shelf its stepper stops at.
     */
    val shelfLeft: Int get() = selectedColor?.stockLeft ?: product?.stockLeft ?: 1

    /** A size has to be chosen when the product has any in stock. */
    val ready: Boolean
        get() = product != null && (sizes.none { it.inStock } || sizeId != null)
}

/**
 * Backs the picker sheet a tile opens instead of adding straight to the cart.
 *
 * The tile only knows the card fields, so the variants are fetched when the
 * sheet opens. The summary at the top is drawn from what the tile already has,
 * which is why the sheet can animate in before this finishes.
 */
@HiltViewModel
class VariantSheetViewModel @Inject constructor(
    private val catalog: CatalogRepository,
    private val cart: CartRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(VariantSheetState())
    val state = _state.asStateFlow()

    fun load(productId: Int) {
        _state.value = VariantSheetState()
        viewModelScope.launch {
            when (val result = catalog.product(productId)) {
                is Outcome.Success -> _state.update {
                    val variants = result.data.variants
                    it.copy(
                        loading = false,
                        product = result.data,
                        // Preselect a colour — there is always one right answer
                        // — but never a size, which is the customer's call.
                        colorId = variants.firstOrNull { v -> v.kind == "color" && v.inStock }?.id,
                    )
                }
                is Outcome.Failure -> _state.update {
                    it.copy(loading = false, error = result.message)
                }
            }
        }
    }

    fun selectSize(id: Int) = _state.update { it.copy(sizeId = id, error = null) }

    fun selectColor(id: Int) = _state.update { it.copy(colorId = id) }

    fun addToCart() {
        val current = _state.value
        val product = current.product ?: return
        if (current.busy) return
        _state.update { it.copy(busy = true, error = null) }
        viewModelScope.launch {
            val result = cart.add(
                productId = product.id,
                variantId = current.sizeId,
                colorVariantId = current.colorId,
                quantity = current.quantity,
            )
            _state.update {
                when (result) {
                    is Outcome.Success -> it.copy(
                        busy = false,
                        // Match on the line we just added so the stepper drives
                        // the right row rather than the product's first one.
                        cartItemId = result.data.items
                            .lastOrNull { item -> item.productId == product.id }
                            ?.id,
                        quantity = result.data.items
                            .lastOrNull { item -> item.productId == product.id }
                            ?.quantity ?: it.quantity,
                    )
                    is Outcome.Failure -> it.copy(busy = false, error = result.message)
                }
            }
        }
    }

    /**
     * Stepper before the line exists: how many to add, held locally.
     *
     * Nothing to patch yet — the line is not in the cart — so this only moves
     * the number the "Savatga" button will send. Bounded by the shelf the
     * choice stands on, the same figure the added state is bounded by.
     */
    fun setPendingQuantity(quantity: Int) = _state.update {
        if (it.cartItemId != null) it
        else it.copy(quantity = quantity.coerceIn(1, it.shelfLeft.coerceAtLeast(1)))
    }

    /** Stepper on the added state; 0 removes the line and returns to choosing. */
    fun setQuantity(quantity: Int) {
        val itemId = _state.value.cartItemId ?: return
        if (quantity !in 0..99 || _state.value.busy) return
        _state.update { it.copy(busy = true, quantity = quantity.coerceAtLeast(1)) }
        viewModelScope.launch {
            val result = if (quantity == 0) cart.remove(itemId) else cart.setQuantity(itemId, quantity)
            _state.update {
                when (result) {
                    is Outcome.Success ->
                        if (quantity == 0) it.copy(busy = false, cartItemId = null, quantity = 1)
                        else it.copy(busy = false)
                    is Outcome.Failure -> it.copy(busy = false, error = result.message)
                }
            }
        }
    }
}
