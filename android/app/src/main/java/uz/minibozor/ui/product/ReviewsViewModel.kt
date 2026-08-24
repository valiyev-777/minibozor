package uz.minibozor.ui.product

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import uz.minibozor.core.util.Outcome
import uz.minibozor.data.remote.dto.ReviewDto
import uz.minibozor.data.remote.dto.ReviewSummaryDto
import uz.minibozor.data.repository.CatalogRepository
import javax.inject.Inject

data class ReviewsState(
    val loading: Boolean = true,
    val summary: ReviewSummaryDto? = null,
    val reviews: List<ReviewDto> = emptyList(),
    val stars: Int? = null,
)

@HiltViewModel
class ReviewsViewModel @Inject constructor(
    private val catalog: CatalogRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(ReviewsState())
    val state = _state.asStateFlow()

    private var productId = 0

    fun load(id: Int) {
        productId = id
        viewModelScope.launch {
            (catalog.reviewSummary(id) as? Outcome.Success)?.let { r ->
                _state.update { it.copy(summary = r.data) }
            }
            fetch()
        }
    }

    fun filter(stars: Int?) {
        _state.update { it.copy(stars = stars) }
        viewModelScope.launch { fetch() }
    }

    fun like(reviewId: Int) {
        viewModelScope.launch {
            val result = catalog.likeReview(reviewId)
            if (result is Outcome.Success) {
                _state.update { state ->
                    state.copy(
                        reviews = state.reviews.map {
                            if (it.id == reviewId) result.data else it
                        }
                    )
                }
            }
        }
    }

    private suspend fun fetch() {
        _state.update { it.copy(loading = true) }
        val result = catalog.reviews(productId, _state.value.stars, 1)
        _state.update {
            it.copy(
                loading = false,
                reviews = (result as? Outcome.Success)?.data?.items ?: emptyList(),
            )
        }
    }
}
