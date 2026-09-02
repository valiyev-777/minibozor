package uz.minibozor.ui.orders

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import uz.minibozor.core.util.Outcome
import uz.minibozor.data.remote.dto.ReturnDto
import uz.minibozor.data.repository.OrderRepository
import javax.inject.Inject

data class ReturnsState(
    val items: List<ReturnDto> = emptyList(),
    val loading: Boolean = true,
    val error: String? = null,
)

@HiltViewModel
class ReturnsViewModel @Inject constructor(
    private val orders: OrderRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(ReturnsState())
    val state = _state.asStateFlow()

    init {
        load()
    }

    fun load() = viewModelScope.launch {
        _state.update { it.copy(loading = true, error = null) }
        when (val result = orders.returns()) {
            is Outcome.Success -> _state.update {
                it.copy(items = result.data, loading = false)
            }
            is Outcome.Failure -> _state.update {
                it.copy(loading = false, error = result.message)
            }
        }
    }
}
