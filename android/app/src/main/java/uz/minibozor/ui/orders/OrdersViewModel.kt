package uz.minibozor.ui.orders

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import uz.minibozor.core.util.Outcome
import uz.minibozor.data.remote.dto.CancelRequest
import uz.minibozor.data.remote.dto.OrderDto
import uz.minibozor.data.remote.dto.OrderSummaryDto
import uz.minibozor.data.remote.dto.ReasonDto
import uz.minibozor.data.remote.dto.ReturnRequestBody
import uz.minibozor.data.repository.OrderRepository
import javax.inject.Inject

data class OrdersState(
    val loading: Boolean = true,
    val activeTab: Boolean = true,
    val orders: List<OrderSummaryDto> = emptyList(),
    val error: String? = null,
)

/** Screen 26 — Buyurtmalarim, split into in-progress and finished. */
@HiltViewModel
class OrdersViewModel @Inject constructor(
    private val repo: OrderRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(OrdersState())
    val state = _state.asStateFlow()

    init {
        load()
    }

    fun selectTab(active: Boolean) {
        _state.update { it.copy(activeTab = active) }
        load()
    }

    fun load() {
        viewModelScope.launch {
            _state.update { it.copy(loading = true, error = null) }
            _state.update {
                when (val result = repo.orders(it.activeTab)) {
                    is Outcome.Success ->
                        it.copy(loading = false, orders = result.data.items)
                    is Outcome.Failure ->
                        it.copy(loading = false, error = result.message)
                }
            }
        }
    }
}

data class OrderDetailState(
    val loading: Boolean = true,
    val order: OrderDto? = null,
    val error: String? = null,
    val reasons: List<ReasonDto> = emptyList(),
    val selectedReasonId: Int? = null,
    val comment: String = "",
    val submitting: Boolean = false,
    val finished: Boolean = false,
)

/** Screens 25, 27, 28 and 29 all read one order; the last two also write. */
@HiltViewModel
class OrderDetailViewModel @Inject constructor(
    private val repo: OrderRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(OrderDetailState())
    val state = _state.asStateFlow()

    private var orderId = 0

    fun load(id: Int) {
        orderId = id
        viewModelScope.launch {
            _state.update { it.copy(loading = true, error = null) }
            _state.update {
                when (val result = repo.order(id)) {
                    is Outcome.Success -> it.copy(loading = false, order = result.data)
                    is Outcome.Failure -> it.copy(loading = false, error = result.message)
                }
            }
        }
    }

    fun retry() = load(orderId)

    fun loadCancelReasons() = loadReasons(cancel = true)

    fun loadReturnReasons() = loadReasons(cancel = false)

    fun selectReason(id: Int) = _state.update { it.copy(selectedReasonId = id) }

    fun setComment(text: String) = _state.update { it.copy(comment = text) }

    fun cancel() {
        val current = _state.value
        if (current.submitting) return
        _state.update { it.copy(submitting = true, error = null) }
        viewModelScope.launch {
            val result = repo.cancel(
                orderId,
                CancelRequest(reasonId = current.selectedReasonId, comment = current.comment),
            )
            _state.update {
                when (result) {
                    is Outcome.Success ->
                        it.copy(submitting = false, finished = true, order = result.data)
                    is Outcome.Failure -> it.copy(submitting = false, error = result.message)
                }
            }
        }
    }

    fun requestReturn() {
        val current = _state.value
        if (current.submitting) return
        _state.update { it.copy(submitting = true, error = null) }
        viewModelScope.launch {
            val result = repo.requestReturn(
                orderId,
                ReturnRequestBody(
                    reasonId = current.selectedReasonId,
                    comment = current.comment,
                ),
            )
            _state.update {
                when (result) {
                    is Outcome.Success -> it.copy(submitting = false, finished = true)
                    is Outcome.Failure -> it.copy(submitting = false, error = result.message)
                }
            }
        }
    }

    private fun loadReasons(cancel: Boolean) {
        viewModelScope.launch {
            val result = if (cancel) repo.cancelReasons() else repo.returnReasons()
            if (result is Outcome.Success) {
                _state.update {
                    it.copy(
                        reasons = result.data,
                        selectedReasonId = it.selectedReasonId ?: result.data.firstOrNull()?.id,
                    )
                }
            }
        }
    }
}
