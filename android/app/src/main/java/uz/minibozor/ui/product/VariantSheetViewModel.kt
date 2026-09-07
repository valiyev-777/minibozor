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

    /**
     * The sizes of the colour chosen, not of the product.
     *
     * A size belongs to a colour and carries that pair's own count, so a shirt
     * in two colours has two sets of size rows. Listed together they put "L" in
     * the sheet twice and let the last black L be added while a white one was
     * still on the shelf.
     */
    val sizes: List<VariantDto>
        get() = product?.variants.orEmpty().filter {
            it.kind == "size" && (it.parentId == null || it.parentId == colorId)
        }

    val selectedColor: VariantDto? get() = colors.firstOrNull { it.id == colorId }
    val selectedSize: VariantDto? get() = sizes.firstOrNull { it.id == sizeId }

    /**
     * How many of the thing actually chosen are left: the colour's share of the
     * shelf, or the whole shelf when the colours are not counted apart. The
     * sheet is adding one colour, so that is the shelf its stepper stops at.
     */
    val shelfLeft: Int
        get() = selectedSize?.stockLeft
            ?: selectedColor?.stockLeft
            ?: product?.stockLeft
            ?: 1

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

    /**
     * A colour, and whatever the size chosen before it now means.
     *
     * Sizes belong to colours, so a size picked under the old colour is a cell
     * of the grid this sheet is no longer showing. The same label is kept where
     * the new colour has it in stock; otherwise the sheet goes back to asking,
     * which is the honest state — the customer has not chosen a size of *this*
     * colour yet.
     */
    fun selectColor(id: Int) = _state.update { s ->
        val ofColor = s.product?.variants.orEmpty()
            .filter { it.kind == "size" && it.parentId == id }
        if (ofColor.isEmpty()) return@update s.copy(colorId = id)
        val kept = s.product?.variants?.firstOrNull { it.id == s.sizeId }?.label
        s.copy(
            colorId = id,
            sizeId = ofColor.firstOrNull { it.label == kept && it.inStock }?.id,
        )
    }

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
            // The line we just added, matched on what we sent rather than on
            // the product: a shirt already in the basket in medium is a line
            // with the same product id, and the stepper would have driven that
            // one instead of the large that was just chosen.
            val added = (result as? Outcome.Success)?.data?.items?.lastOrNull { item ->
                item.productId == product.id &&
                    item.variantId == current.sizeId &&
                    item.colorVariantId == current.colorId
            }
            _state.update {
                when (result) {
                    is Outcome.Success -> it.copy(
                        busy = false,
                        cartItemId = added?.id,
                        quantity = added?.quantity ?: it.quantity,
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
