package uz.minibozor.ui.checkout

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import uz.minibozor.core.util.Outcome
import uz.minibozor.data.remote.dto.AddressRequest
import uz.minibozor.data.repository.OrderRepository
import javax.inject.Inject

data class AddressFormState(
    val saving: Boolean = false,
    val error: String? = null,
    val savedId: Int? = null,
)

/**
 * Screen 20 — "Manzil qo'shish".
 *
 * Reached both from the profile and from checkout, so it owns its own saving
 * rather than borrowing the checkout draft: adding an address from the profile
 * must not drop anyone into an order.
 */
@HiltViewModel
class AddressFormViewModel @Inject constructor(
    private val orders: OrderRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(AddressFormState())
    val state = _state.asStateFlow()

    fun save(body: AddressRequest) {
        if (_state.value.saving) return
        _state.update { it.copy(saving = true, error = null) }
        viewModelScope.launch {
            _state.update {
                when (val result = orders.createAddress(body)) {
                    is Outcome.Success -> it.copy(saving = false, savedId = result.data.id)
                    is Outcome.Failure -> it.copy(saving = false, error = result.message)
                }
            }
        }
    }
}
