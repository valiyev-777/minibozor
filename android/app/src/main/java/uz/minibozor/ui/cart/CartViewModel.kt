package uz.minibozor.ui.cart

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import uz.minibozor.core.util.Outcome
import uz.minibozor.data.remote.dto.CartDto
import uz.minibozor.data.repository.CartRepository
import javax.inject.Inject

data class CartUiState(
    val loading: Boolean = true,
    val cart: CartDto? = null,
    val error: String? = null,
    val promoInput: String = "",
    val promoError: String? = null,
)

/** Screens 17 and 18. */
@HiltViewModel
class CartViewModel @Inject constructor(
    private val repo: CartRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(CartUiState())
    val state = _state.asStateFlow()

    init {
        refresh()
    }

    fun refresh() {
        viewModelScope.launch {
            _state.update { it.copy(loading = true, error = null) }
            _state.update {
                when (val result = repo.refresh()) {
                    is Outcome.Success -> it.copy(loading = false, cart = result.data)
                    is Outcome.Failure -> it.copy(loading = false, error = result.message)
                }
            }
        }
    }

    fun setQuantity(itemId: Int, quantity: Int) = mutate { repo.setQuantity(itemId, quantity) }

    fun setSelected(itemId: Int, selected: Boolean) = mutate { repo.setSelected(itemId, selected) }

    fun remove(itemId: Int) = mutate { repo.remove(itemId) }

    fun onPromoChange(code: String) =
        _state.update { it.copy(promoInput = code, promoError = null) }

    fun applyPromo() {
        val code = _state.value.promoInput.trim()
        if (code.isEmpty()) return
        viewModelScope.launch {
            _state.update {
                when (val result = repo.applyPromo(code)) {
                    is Outcome.Success -> it.copy(cart = result.data, promoError = null)
                    is Outcome.Failure -> it.copy(promoError = result.message)
                }
            }
        }
    }

    private fun mutate(block: suspend () -> Outcome<CartDto>) {
        viewModelScope.launch {
            val result = block()
            if (result is Outcome.Success) _state.update { it.copy(cart = result.data) }
        }
    }
}
