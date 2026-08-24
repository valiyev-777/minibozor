package uz.minibozor.ui.home

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import uz.minibozor.core.util.Outcome
import uz.minibozor.data.local.AppPrefs
import uz.minibozor.data.remote.dto.HomeDto
import uz.minibozor.data.repository.CartRepository
import uz.minibozor.data.repository.CatalogRepository
import uz.minibozor.ui.common.UiState
import javax.inject.Inject

@HiltViewModel
class HomeViewModel @Inject constructor(
    private val catalog: CatalogRepository,
    private val cart: CartRepository,
    prefs: AppPrefs,
) : ViewModel() {

    private val _state = MutableStateFlow<UiState<HomeDto>>(UiState.Loading)
    val state: StateFlow<UiState<HomeDto>> = _state.asStateFlow()

    val cartBadge: StateFlow<Int> = cart.cart
        .map { it?.totals?.itemsCount ?: 0 }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), 0)

    val city: StateFlow<String> =
        prefs.city.stateIn(viewModelScope, SharingStarted.Eagerly, "Toshkent")

    init {
        load()
        viewModelScope.launch { cart.refresh() }
    }

    fun load() {
        viewModelScope.launch {
            _state.value = UiState.Loading
            _state.value = when (val result = catalog.home(city.value)) {
                is Outcome.Success -> UiState.Ready(result.data)
                is Outcome.Failure -> UiState.Error(result.message)
            }
        }
    }

    fun toggleFavorite(productId: Int, current: Boolean) {
        viewModelScope.launch {
            catalog.setFavorite(productId, !current)
            // The home payload carries `is_favorite`, so a reload keeps every
            // tile on the screen in sync rather than just the one tapped.
            reloadQuietly()
        }
    }

    fun addToCart(productId: Int, onDone: (String) -> Unit) {
        viewModelScope.launch {
            when (val result = cart.add(productId, null)) {
                is Outcome.Success -> onDone("Savatga qo'shildi")
                is Outcome.Failure -> onDone(result.message)
            }
        }
    }

    private suspend fun reloadQuietly() {
        val result = catalog.home(city.value)
        if (result is Outcome.Success) _state.value = UiState.Ready(result.data)
    }
}
