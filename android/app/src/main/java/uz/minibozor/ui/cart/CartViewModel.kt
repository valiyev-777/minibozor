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

    /** The code the basket is currently priced with, or null. */
    val promoCode: StateFlow<String?> = repo.promoCode

    private val _loading = MutableStateFlow(true)
    val loading = _loading.asStateFlow()

    private val _error = MutableStateFlow<String?>(null)
    val error = _error.asStateFlow()

    /**
     * Why the last promo code was refused, in the server's own words.
     *
     * Separate from [error], which is about the basket itself. A code being
     * wrong is not the cart failing to load, and showing "Promokod yaroqsiz"
     * where the retry button lives would say the wrong thing about both.
     */
    private val _promoError = MutableStateFlow<String?>(null)
    val promoError = _promoError.asStateFlow()

    private val _promoBusy = MutableStateFlow(false)
    val promoBusy = _promoBusy.asStateFlow()

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

    fun setAllSelected(selected: Boolean) = mutate { repo.setAllSelected(selected) }

    fun applyPromo(code: String) {
        val trimmed = code.trim()
        if (trimmed.isEmpty() || _promoBusy.value) return
        _promoBusy.value = true
        _promoError.value = null
        viewModelScope.launch {
            when (val result = repo.applyPromo(trimmed)) {
                is Outcome.Success -> Unit
                is Outcome.Failure -> _promoError.value = result.message
            }
            _promoBusy.value = false
        }
    }

    fun clearPromo() {
        _promoError.value = null
        mutate { repo.clearPromo() }
    }

    fun setSelected(itemId: Int, selected: Boolean) = mutate { repo.setSelected(itemId, selected) }

    fun remove(itemId: Int) = mutate { repo.remove(itemId) }

    private fun mutate(block: suspend () -> Outcome<CartDto>) {
        viewModelScope.launch {
            val result = block()
            if (result is Outcome.Failure) _error.update { result.message }
        }
    }
}
