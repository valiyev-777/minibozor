package uz.minibozor.ui.cart

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import uz.minibozor.core.util.Outcome
import uz.minibozor.data.remote.dto.CartDto
import uz.minibozor.data.repository.CartRepository
import javax.inject.Inject

/**
 * Screens 17 and 18.
 *
 * The cart itself is read straight from [CartRepository] rather than copied into
 * local state: adding from the home screen or a product page has to show up here
 * without the user first poking something on this screen.
 */
@HiltViewModel
class CartViewModel @Inject constructor(
    private val repo: CartRepository,
) : ViewModel() {

    val cart: StateFlow<CartDto?> = repo.cart

    private val _loading = MutableStateFlow(true)
    val loading = _loading.asStateFlow()

    private val _error = MutableStateFlow<String?>(null)
    val error = _error.asStateFlow()

    init {
        refresh()
    }

    fun refresh() {
        viewModelScope.launch {
            _loading.value = repo.cart.value == null
            _error.value = null
            when (val result = repo.refresh()) {
                is Outcome.Success -> Unit          // the repository holds it
                is Outcome.Failure -> _error.value = result.message
            }
            _loading.value = false
        }
    }

    fun setQuantity(itemId: Int, quantity: Int) = mutate { repo.setQuantity(itemId, quantity) }

    fun setSelected(itemId: Int, selected: Boolean) = mutate { repo.setSelected(itemId, selected) }

    fun remove(itemId: Int) = mutate { repo.remove(itemId) }

    private fun mutate(block: suspend () -> Outcome<CartDto>) {
        viewModelScope.launch {
            val result = block()
            if (result is Outcome.Failure) _error.update { result.message }
        }
    }
}
