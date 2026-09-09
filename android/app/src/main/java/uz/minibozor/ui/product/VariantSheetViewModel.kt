package uz.minibozor.ui.product

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import uz.minibozor.core.util.Outcome
import uz.minibozor.data.remote.dto.ColourDto
import uz.minibozor.data.remote.dto.ProductDto
import uz.minibozor.data.remote.dto.VariantDto
import uz.minibozor.data.repository.CartRepository
import uz.minibozor.data.repository.CatalogRepository
import javax.inject.Inject

data class VariantSheetState(
    val loading: Boolean = true,
    val product: ProductDto? = null,
    /** The cell chosen — one colour, one size, and the thing added to a cart. */
    val variantId: Int? = null,
    /** The colour chosen, by name: a colour has no id and needs none. */
    val colour: String? = null,
    val quantity: Int = 1,
    /** Set once the line is in the cart; the bottom bar becomes a stepper. */
    val cartItemId: Int? = null,
    val busy: Boolean = false,
    val error: String? = null,
) {
    /** Only the colours worth asking about: a card with none has one blank. */
    val colours: List<ColourDto>
        get() = product?.colours.orEmpty().filter { it.colour.isNotBlank() }

    /**
     * The cells of the colour chosen, not of the product.
     *
     * A cell is a colour and a size together and carries that pair's own count,
     * so a shirt in two colours has two sets of size rows. Listed together they
     * put "L" in the sheet twice and let the last black L be added while a
     * white one was still on the shelf.
     */
    val sizes: List<VariantDto>
        get() = product?.variants.orEmpty()
            .filter { (colour == null || it.colour == colour) && it.size.isNotBlank() }

    val selected: VariantDto?
        get() = product?.variants.orEmpty().firstOrNull { it.id == variantId }

    /**
     * How many of the thing actually chosen are left.
     *
     * The cell's own count where one is chosen — it is already "what can be
     * bought", the shelf less what is promised — and the colour's cells added
     * up before that. The sheet is adding one cell, so that is the shelf its
     * stepper stops at.
     */
    val shelfLeft: Int
        get() = selected?.stockLeft
            ?: product?.variants.orEmpty()
                .filter { colour == null || it.colour == colour }
                .sumOf { it.stockLeft }
                .takeIf { it > 0 }
            ?: product?.stockLeft
            ?: 1

    /** A cell has to be chosen where there is a choice of size to make. */
    val ready: Boolean
        get() = product != null && (sizes.none { it.inStock } || variantId != null)
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
                    val product = result.data
                    val colour = product.colours.firstOrNull { c -> c.inStock }
                        ?: product.colours.firstOrNull()
                    // A product with nothing to choose has one cell, and asking
                    // the customer to pick it is asking a question with one
                    // answer. Anything with sizes leaves the size to them.
                    val only = product.variants.singleOrNull()
                    it.copy(
                        loading = false,
                        product = product,
                        colour = colour?.colour,
                        variantId = only?.id,
                    )
                }
                is Outcome.Failure -> _state.update {
                    it.copy(loading = false, error = result.message)
                }
            }
        }
    }

    fun selectSize(id: Int) = _state.update { it.copy(variantId = id, error = null) }

    /**
     * A colour, and whatever the size chosen before it now means.
     *
     * A cell is a colour *and* a size, so the one picked under the old colour
     * buys something this sheet is no longer showing. The same size is kept
     * where the new colour has it in stock; otherwise the sheet goes back to
     * asking, which is the honest state — the customer has not chosen a size of
     * *this* colour yet.
     */
    fun selectColour(colour: String) = _state.update { s ->
        val cells = s.product?.variants.orEmpty().filter { it.colour == colour }
        if (cells.isEmpty()) return@update s.copy(colour = colour)
        val kept = s.selected?.size
        s.copy(
            colour = colour,
            variantId = cells.firstOrNull { it.size == kept && it.inStock }?.id,
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
                variantId = current.variantId,
                quantity = current.quantity,
            )
            // The line we just added, matched on what we sent rather than on
            // the product: a shirt already in the basket in medium is a line
            // with the same product id, and the stepper would have driven that
            // one instead of the large that was just chosen.
            val added = (result as? Outcome.Success)?.data?.items?.lastOrNull { item ->
                item.productId == product.id && item.variantId == current.variantId
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
