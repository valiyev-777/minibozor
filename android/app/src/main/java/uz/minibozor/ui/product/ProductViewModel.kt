package uz.minibozor.ui.product

import uz.minibozor.core.util.Features
import uz.minibozor.core.util.AppStrings
import uz.minibozor.R
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import uz.minibozor.core.util.Outcome
import uz.minibozor.data.remote.dto.CartItemDto
import uz.minibozor.data.remote.dto.ProductCardDto
import uz.minibozor.data.remote.dto.ProductDto
import uz.minibozor.data.remote.dto.VariantDto
import uz.minibozor.data.remote.dto.ReviewDto
import uz.minibozor.data.remote.dto.ReviewSummaryDto
import uz.minibozor.data.repository.CartRepository
import uz.minibozor.data.repository.CatalogRepository
import javax.inject.Inject

data class ProductState(
    val loading: Boolean = true,
    val error: String? = null,
    val product: ProductDto? = null,
    val summary: ReviewSummaryDto? = null,
    val topReviews: List<ReviewDto> = emptyList(),
    val similar: List<ProductCardDto> = emptyList(),
    /**
     * The colour chosen, by name.
     *
     * A colour has no id any more and does not need one: it is a property of
     * the cells, and the cells are what get bought. `colours` on the product
     * carries the photograph and the swatch for each one.
     */
    val selectedColour: String? = null,
    /** The cell chosen — one colour, one size, and the thing added to a cart. */
    val selectedVariantId: Int? = null,
    val adding: Boolean = false,
) {
    /** The sizes of the colour chosen, in the order the server sent them. */
    val sizes: List<VariantDto>
        get() = product?.variants.orEmpty().filter {
            selectedColour == null || it.colour == selectedColour
        }

    val selectedVariant: VariantDto?
        get() = product?.variants.orEmpty().firstOrNull { it.id == selectedVariantId }
}

/** Screen 14. */
@HiltViewModel
class ProductViewModel @Inject constructor(
    private val catalog: CatalogRepository,
    private val cart: CartRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(ProductState())
    val state = _state.asStateFlow()

    /** Drives the badge and the pulse on the header cart button. */
    val cartCount: StateFlow<Int> = cart.cart
        .map { it?.totals?.itemsCount ?: 0 }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), 0)

    private var productId: Int = 0

    fun load(id: Int) {
        productId = id
        viewModelScope.launch {
            _state.update { it.copy(loading = true, error = null) }
            when (val result = catalog.product(id)) {
                is Outcome.Success -> {
                    val product = result.data
                    // The colour first, then a cell *of that colour*: a cell
                    // carries its own count, so preselecting the product's
                    // first in-stock cell could land on a colour the page is
                    // not showing.
                    val colour = product.colours.firstOrNull { it.inStock }
                        ?: product.colours.firstOrNull()
                    _state.update {
                        it.copy(
                            loading = false,
                            product = product,
                            selectedColour = colour?.colour,
                            selectedVariantId = product.variants
                                .firstOrNull { v ->
                                    v.inStock && (colour == null || v.colour == colour.colour)
                                }?.id,
                        )
                    }
                }
                is Outcome.Failure ->
                    _state.update { it.copy(loading = false, error = result.message) }
            }
        }
        viewModelScope.launch {
            // Both of these answer 404 while reviews are off, and the failure
            // was already being swallowed — but a 404 swallowed on every
            // product page open is still two round-trips and two lines of
            // noise in the server's log. See core/util/Features.kt.
            if (Features.REVIEWS) {
                (catalog.reviewSummary(id) as? Outcome.Success)?.let { r ->
                    _state.update { it.copy(summary = r.data) }
                }
                (catalog.reviews(id, null, 1) as? Outcome.Success)?.let { r ->
                    _state.update { it.copy(topReviews = r.data.items.take(2)) }
                }
            }
            (catalog.similar(id) as? Outcome.Success)?.let { r ->
                _state.update { it.copy(similar = r.data) }
            }
        }
    }

    fun retry() = load(productId)

    fun selectSize(id: Int) = _state.update { it.copy(selectedVariantId = id) }

    /**
     * A colour, and the cell that goes with it.
     *
     * A cell is a colour *and* a size, so the one chosen a moment ago belongs
     * to the colour being left behind — kept, it would buy the wrong thing.
     *
     * **The size survives the change of colour even where it has sold out.** It
     * used to be kept only while the new colour had it in stock and to fall
     * back to whatever that colour did have, which quietly moved the customer
     * off the size they came for: pick 41, tap through the colours, and you end
     * up holding a 44 without being told. Now 41 stays 41, the chip is struck
     * through, and the strip of photographs says which colours have it — that
     * is the answer the tapping was trying to get at. Only a colour that does
     * not come in this size at all forces a different one.
     */
    fun selectColour(colour: String) = _state.update { s ->
        val cells = s.product?.variants.orEmpty().filter { it.colour == colour }
        if (cells.isEmpty()) return@update s.copy(selectedColour = colour)
        val kept = s.selectedVariant?.size
        val next = cells.firstOrNull { it.size == kept }
            ?: cells.firstOrNull { it.inStock }
            ?: cells.first()
        s.copy(selectedColour = colour, selectedVariantId = next.id)
    }

    fun toggleFavorite() {
        val product = _state.value.product ?: return
        viewModelScope.launch {
            catalog.setFavorite(product.id, !product.isFavorite)
            _state.update { it.copy(product = product.copy(isFavorite = !product.isFavorite)) }
        }
    }

    /**
     * The cart line for what the page is showing right now, if it is in the
     * cart. The buy bar swaps its button for a quantity stepper off this, which
     * is also what stops a burst of taps from piling copies into the cart.
     *
     * The size and the colour are part of the question, and they were not.
     * Matching on the product alone meant a watch already in the basket in
     * 41 mm turned the bar into a stepper for that line — and it stayed a
     * stepper when the customer then picked 36 mm, so there was no button left
     * to buy the second size with. One line per size is what the basket holds
     * and what the server folds adds into; the bar has to ask the same
     * question the server answers.
     */
    val cartLine: StateFlow<CartItemDto?> =
        combine(cart.cart, _state) { c, s ->
            c?.items?.lastOrNull {
                it.productId == productId && it.variantId == s.selectedVariantId
            }
        }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), null)

    fun addToCart(onDone: (String) -> Unit) {
        val current = _state.value
        val product = current.product ?: return
        // One request at a time: taps landing while this one is in flight are
        // dropped instead of queueing more adds.
        if (current.adding) return
        _state.update { it.copy(adding = true) }
        viewModelScope.launch {
            // One id, because one cell is one colour and one size. It used to
            // be two that could disagree with each other.
            val result = cart.add(
                productId = product.id,
                variantId = current.selectedVariantId,
            )
            _state.update { it.copy(adding = false) }
            onDone(
                when (result) {
                    is Outcome.Success -> AppStrings[R.string.savatga_qoshildi]
                    is Outcome.Failure -> result.message
                }
            )
        }
    }

    /** Stepper on the buy bar; zero removes the line and brings the button back. */
    fun setCartQuantity(itemId: Int, quantity: Int) {
        if (_state.value.adding) return
        _state.update { it.copy(adding = true) }
        viewModelScope.launch {
            if (quantity <= 0) cart.remove(itemId) else cart.setQuantity(itemId, quantity)
            _state.update { it.copy(adding = false) }
        }
    }
}
