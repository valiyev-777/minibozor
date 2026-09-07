package uz.minibozor.ui.catalog

import uz.minibozor.core.util.AppStrings
import uz.minibozor.R
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import uz.minibozor.core.util.Outcome
import uz.minibozor.data.remote.dto.FiltersDto
import uz.minibozor.data.remote.dto.ProductCardDto
import uz.minibozor.data.repository.CartRepository
import uz.minibozor.data.repository.CatalogRepository
import javax.inject.Inject

data class ListingState(
    val query: ProductQuery = ProductQuery(),
    val items: List<ProductCardDto> = emptyList(),
    val total: Int = 0,
    val page: Int = 1,
    val hasMore: Boolean = false,
    val loading: Boolean = true,
    val loadingMore: Boolean = false,
    val error: String? = null,
    val filters: FiltersDto? = null,
)

/** Screens 09 and 12 — the same grid, with or without a search term. */
@HiltViewModel
class ListingViewModel @Inject constructor(
    private val catalog: CatalogRepository,
    private val cart: CartRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(ListingState())
    val state = _state.asStateFlow()

    fun start(category: String?, text: String?) {
        if (_state.value.items.isNotEmpty()) return
        _state.update { it.copy(query = it.query.copy(category = category, text = text)) }
        reload()
        loadFilters()
    }

    fun apply(query: ProductQuery) {
        _state.update { it.copy(query = query) }
        reload()
    }

    fun setSort(sort: String) = apply(_state.value.query.copy(sort = sort))

    fun reload() {
        viewModelScope.launch {
            _state.update { it.copy(loading = true, error = null, page = 1) }
            when (val result = catalog.products(_state.value.query, page = 1)) {
                is Outcome.Success -> _state.update {
                    it.copy(
                        loading = false,
                        items = result.data.items,
                        total = result.data.total,
                        hasMore = result.data.hasMore,
                        page = 1,
                    )
                }
                is Outcome.Failure ->
                    _state.update { it.copy(loading = false, error = result.message) }
            }
        }
    }

    fun loadMore() {
        val current = _state.value
        if (!current.hasMore || current.loadingMore || current.loading) return

        viewModelScope.launch {
            _state.update { it.copy(loadingMore = true) }
            when (val result = catalog.products(current.query, page = current.page + 1)) {
                is Outcome.Success -> _state.update {
                    it.copy(
                        loadingMore = false,
                        items = it.items + result.data.items,
                        page = it.page + 1,
                        hasMore = result.data.hasMore,
                    )
                }
                is Outcome.Failure -> _state.update { it.copy(loadingMore = false) }
            }
        }
    }

    fun toggleFavorite(product: ProductCardDto) {
        viewModelScope.launch {
            catalog.setFavorite(product.id, !product.isFavorite)
            _state.update { state ->
                state.copy(
                    items = state.items.map {
                        if (it.id == product.id) it.copy(isFavorite = !product.isFavorite) else it
                    }
                )
            }
        }
    }

    private fun loadFilters() {
        viewModelScope.launch {
            val result = catalog.filters(_state.value.query.category)
            if (result is Outcome.Success) _state.update { it.copy(filters = result.data) }
        }
    }
}
