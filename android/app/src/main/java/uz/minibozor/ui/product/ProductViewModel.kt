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
import uz.minibozor.data.remote.dto.OfferDto
import uz.minibozor.data.remote.dto.ProductCardDto
import uz.minibozor.data.remote.dto.ProductDto
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
     * Every seller offering this product, cheapest first.
     *
     * Empty while it is being fetched and on a product only the house sells, so
     * the page shows the section when there is more than one of them and says
     * nothing otherwise.
     */
    val offers: List<OfferDto> = emptyList(),
    val selectedSizeId: Int? = null,
    val selectedColorId: Int? = null,
    val adding: Boolean = false,
)

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
                    // The colour first, then a size *of that colour*: sizes
                    // are counted per colour, so preselecting the product's
                    // first in-stock size could land on a size belonging to a
                    // colour the page is not showing.
                    val color = product.variants.firstOrNull { v -> v.kind == "color" }
                    _state.update {
                        it.copy(
                            loading = false,
                            product = product,
                            selectedColorId = color?.id,
                            selectedSizeId = product.variants
                                .firstOrNull { v ->
                                    v.kind == "size" && v.inStock &&
                                        (v.parentId == null || v.parentId == color?.id)
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
            // Alongside the rest of the page rather than gating it: a product
            // page whose price and photographs have arrived should draw, and
            // the list of sellers is an addition to it, not a precondition.
            (catalog.offers(id) as? Outcome.Success)?.let { r ->
                _state.update { it.copy(offers = r.data) }
            }
        }
    }

    fun retry() = load(productId)

    fun selectSize(id: Int) = _state.update { it.copy(selectedSizeId = id) }

    /**
     * A colour, and the size that goes with it.
     *
     * Sizes belong to colours, so the size chosen a moment ago was a size of
     * the colour being left behind — held on to, it would buy a cell of the
     * grid the page is no longer showing. The same label is kept where the new
     * colour has it in stock, which is what a customer switching between two
     * colours of the same shirt means to happen; otherwise the first size the
     * new colour actually has.
     */
    fun selectColor(id: Int) = _state.update { s ->
        val ofColor = s.product?.variants.orEmpty()
            .filter { it.kind == "size" && it.parentId == id }
        if (ofColor.isEmpty()) return@update s.copy(selectedColorId = id)
        val kept = s.product?.variants?.firstOrNull { it.id == s.selectedSizeId }?.label
        val next = ofColor.firstOrNull { it.label == kept && it.inStock }
            ?: ofColor.firstOrNull { it.inStock }
        s.copy(selectedColorId = id, selectedSizeId = next?.id)
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
                it.productId == productId &&
                    it.variantId == s.selectedSizeId &&
                    it.colorVariantId == s.selectedColorId
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
            // Both, not one of the two: a cart line carries a size *and* a
            // colour, and the picker sheet already sends both. Sending only the
            // size here made the same shirt land as a second line with its
            // colour lost.
            val result = cart.add(
                productId = product.id,
                variantId = current.selectedSizeId,
                colorVariantId = current.selectedColorId,
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
