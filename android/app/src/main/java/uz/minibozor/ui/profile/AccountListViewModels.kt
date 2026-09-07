package uz.minibozor.ui.profile

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
import uz.minibozor.data.remote.dto.AddressDto
import uz.minibozor.data.remote.dto.CardDto
import uz.minibozor.data.remote.dto.NotificationGroupDto
import uz.minibozor.data.remote.dto.ProductCardDto
import uz.minibozor.data.remote.dto.ReviewDto
import uz.minibozor.data.repository.CartRepository
import uz.minibozor.data.repository.CatalogRepository
import uz.minibozor.data.repository.OrderRepository
import uz.minibozor.data.repository.ProfileRepository
import javax.inject.Inject

/** Screen 32 — To'lov kartalari. */
@HiltViewModel
class CardsViewModel @Inject constructor(
    private val repo: OrderRepository,
) : ViewModel() {

    private val _cards = MutableStateFlow<List<CardDto>>(emptyList())
    val cards = _cards.asStateFlow()

    init {
        load()
    }

    fun load() = viewModelScope.launch {
        (repo.cards() as? Outcome.Success)?.let { _cards.value = it.data }
    }

    fun makeDefault(id: Int) = viewModelScope.launch {
        repo.makeCardDefault(id)
        load()
    }

    fun delete(id: Int) = viewModelScope.launch {
        repo.deleteCard(id)
        load()
    }
}

/** Screen 33 — Manzillarim. */
@HiltViewModel
class AddressesViewModel @Inject constructor(
    private val repo: OrderRepository,
) : ViewModel() {

    private val _addresses = MutableStateFlow<List<AddressDto>>(emptyList())
    val addresses = _addresses.asStateFlow()

    init {
        load()
    }

    fun load() = viewModelScope.launch {
        (repo.addresses() as? Outcome.Success)?.let { _addresses.value = it.data }
    }

    fun delete(id: Int) = viewModelScope.launch {
        repo.deleteAddress(id)
        load()
    }
}

/** Screen 34 — Sharhlarim. */
@HiltViewModel
class MyReviewsViewModel @Inject constructor(
    private val repo: ProfileRepository,
) : ViewModel() {

    private val _reviews = MutableStateFlow<List<ReviewDto>>(emptyList())
    val reviews = _reviews.asStateFlow()

    init {
        load()
    }

    fun load() = viewModelScope.launch {
        (repo.myReviews() as? Outcome.Success)?.let { _reviews.value = it.data.items }
    }

    fun delete(id: Int) = viewModelScope.launch {
        repo.deleteReview(id)
        load()
    }
}

/** Screen 35 — Sevimlilar. */
@HiltViewModel
class FavoritesViewModel @Inject constructor(
    private val catalog: CatalogRepository,
    private val cart: CartRepository,
) : ViewModel() {

    private val _items = MutableStateFlow<List<ProductCardDto>>(emptyList())
    val items = _items.asStateFlow()

    private val _loading = MutableStateFlow(true)
    val loading = _loading.asStateFlow()

    init {
        load()
    }

    fun load() = viewModelScope.launch {
        _loading.value = true
        (catalog.favorites(1) as? Outcome.Success)?.let { _items.value = it.data.items }
        _loading.value = false
    }

    fun remove(productId: Int) = viewModelScope.launch {
        catalog.setFavorite(productId, false)
        _items.update { list -> list.filterNot { it.id == productId } }
    }
}

/** Screen 36 — Bildirishnomalar. */
@HiltViewModel
class NotificationsViewModel @Inject constructor(
    private val repo: ProfileRepository,
) : ViewModel() {

    private val _groups = MutableStateFlow<List<NotificationGroupDto>>(emptyList())
    val groups = _groups.asStateFlow()

    init {
        load()
    }

    fun load() = viewModelScope.launch {
        (repo.notifications() as? Outcome.Success)?.let { _groups.value = it.data }
    }

    fun markAllRead() = viewModelScope.launch {
        repo.markNotificationsRead()
        load()
    }
}
