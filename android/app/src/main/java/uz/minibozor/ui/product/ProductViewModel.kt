package uz.minibozor.ui.product

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
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import uz.minibozor.core.util.Outcome
import uz.minibozor.data.remote.dto.CartItemDto
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
                    _state.update {
                        it.copy(
                            loading = false,
                            product = product,
                            // Preselect the first in-stock size, as the design shows.
                            selectedSizeId = product.variants
                                .firstOrNull { v -> v.kind == "size" && v.inStock }?.id,
                            selectedColorId = product.variants
                                .firstOrNull { v -> v.kind == "color" }?.id,
                        )
                    }
                }
                is Outcome.Failure ->
                    _state.update { it.copy(loading = false, error = result.message) }
            }
        }
        viewModelScope.launch {
            (catalog.reviewSummary(id) as? Outcome.Success)?.let { r ->
                _state.update { it.copy(summary = r.data) }
            }
            (catalog.reviews(id, null, 1) as? Outcome.Success)?.let { r ->
                _state.update { it.copy(topReviews = r.data.items.take(2)) }
            }
            (catalog.similar(id) as? Outcome.Success)?.let { r ->
                _state.update { it.copy(similar = r.data) }
            }
        }
    }

    fun retry() = load(productId)

    fun selectSize(id: Int) = _state.update { it.copy(selectedSizeId = id) }

    fun selectColor(id: Int) = _state.update { it.copy(selectedColorId = id) }

    fun toggleFavorite() {
        val product = _state.value.product ?: return
        viewModelScope.launch {
            catalog.setFavorite(product.id, !product.isFavorite)
            _state.update { it.copy(product = product.copy(isFavorite = !product.isFavorite)) }
        }
    }

    /**
     * The cart line for this product, if it is already in the cart. The buy bar
     * swaps its button for a quantity stepper off this, which is also what
     * stops a burst of taps from piling copies into the cart.
     */
    val cartLine: StateFlow<CartItemDto?> = cart.cart
        .map { c -> c?.items?.lastOrNull { it.productId == productId } }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), null)

    fun addToCart(onDone: (String) -> Unit) {
        val current = _state.value
        val product = current.product ?: return
        // One request at a time: taps landing while this one is in flight are
        // dropped instead of queueing more adds.
        if (current.adding) return
        _state.update { it.copy(adding = true) }
        viewModelScope.launch {
            val variantId = current.selectedSizeId ?: current.selectedColorId
            val result = cart.add(product.id, variantId)
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
