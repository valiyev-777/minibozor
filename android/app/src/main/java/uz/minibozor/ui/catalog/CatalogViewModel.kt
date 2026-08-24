package uz.minibozor.ui.catalog

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import uz.minibozor.core.util.Outcome
import uz.minibozor.data.remote.dto.CategoryDto
import uz.minibozor.data.repository.CatalogRepository
import uz.minibozor.ui.common.UiState
import javax.inject.Inject

/** Screen 10 — the flat list of root categories. */
@HiltViewModel
class CatalogViewModel @Inject constructor(
    private val catalog: CatalogRepository,
) : ViewModel() {

    private val _state = MutableStateFlow<UiState<List<CategoryDto>>>(UiState.Loading)
    val state = _state.asStateFlow()

    init {
        load()
    }

    fun load() {
        viewModelScope.launch {
            _state.value = UiState.Loading
            _state.value = when (val result = catalog.rootCategories()) {
                is Outcome.Success -> UiState.Ready(result.data)
                is Outcome.Failure -> UiState.Error(result.message)
            }
        }
    }
}

/** Screen 11 — one category's children, shown as image tiles. */
@HiltViewModel
class SubcategoryViewModel @Inject constructor(
    private val catalog: CatalogRepository,
) : ViewModel() {

    private val _state = MutableStateFlow<UiState<Pair<CategoryDto, List<CategoryDto>>>>(UiState.Loading)
    val state = _state.asStateFlow()

    private var slug: String = ""

    fun load(slug: String) {
        this.slug = slug
        viewModelScope.launch {
            _state.value = UiState.Loading
            val parent = catalog.category(slug)
            val children = catalog.children(slug)
            _state.value = when {
                parent is Outcome.Success && children is Outcome.Success ->
                    UiState.Ready(parent.data to children.data)
                parent is Outcome.Failure -> UiState.Error(parent.message)
                children is Outcome.Failure -> UiState.Error(children.message)
                else -> UiState.Error("Turkumni yuklab bo'lmadi")
            }
        }
    }

    fun retry() = load(slug)
}
