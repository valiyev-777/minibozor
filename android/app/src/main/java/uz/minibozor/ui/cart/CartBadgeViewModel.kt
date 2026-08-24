package uz.minibozor.ui.cart

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import uz.minibozor.data.repository.CartRepository
import javax.inject.Inject

/**
 * Just the number on the tab bar. Reads the shared cart, so adding from any
 * screen updates the badge without that screen knowing about it.
 */
@HiltViewModel
class CartBadgeViewModel @Inject constructor(
    private val repo: CartRepository,
) : ViewModel() {

    val count: StateFlow<Int> = repo.cart
        .map { it?.totals?.itemsCount ?: 0 }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), 0)

    init {
        if (repo.cart.value == null) {
            viewModelScope.launch { repo.refresh() }
        }
    }
}
