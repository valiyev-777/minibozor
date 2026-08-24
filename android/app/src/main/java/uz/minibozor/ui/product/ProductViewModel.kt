package uz.minibozor.ui.product

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import uz.minibozor.core.util.Outcome
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

    fun addToCart(onDone: (String) -> Unit) {
        val current = _state.value
        val product = current.product ?: return
        _state.update { it.copy(adding = true) }
        viewModelScope.launch {
            val variantId = current.selectedSizeId ?: current.selectedColorId
            val result = cart.add(product.id, variantId)
            _state.update { it.copy(adding = false) }
            onDone(
                when (result) {
                    is Outcome.Success -> "Savatga qo'shildi"
                    is Outcome.Failure -> result.message
                }
            )
        }
    }
}
