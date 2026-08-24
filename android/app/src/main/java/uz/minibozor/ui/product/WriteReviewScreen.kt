package uz.minibozor.ui.product

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import uz.minibozor.core.util.Outcome
import uz.minibozor.data.remote.dto.ReviewCreateRequest
import uz.minibozor.data.repository.CatalogRepository
import javax.inject.Inject

data class WriteReviewState(
    val rating: Int = 5,
    val text: String = "",
    val tags: List<String> = emptyList(),
    val selectedTags: Set<String> = emptySet(),
    val submitting: Boolean = false,
    val error: String? = null,
    val done: Boolean = false,
)

@HiltViewModel
class WriteReviewViewModel @Inject constructor(
    private val catalog: CatalogRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(WriteReviewState())
    val state = _state.asStateFlow()

    init {
        viewModelScope.launch {
            (catalog.reviewTags() as? Outcome.Success)?.let { r ->
                _state.update { it.copy(tags = r.data) }
            }
        }
    }

    fun setRating(rating: Int) = _state.update { it.copy(rating = rating) }

    fun setText(text: String) = _state.update { it.copy(text = text) }

    fun toggleTag(tag: String) = _state.update {
        it.copy(
            selectedTags = if (tag in it.selectedTags) it.selectedTags - tag
            else it.selectedTags + tag
        )
    }

    fun submit(productId: Int, orderItemId: Int?) {
        val current = _state.value
        if (current.submitting) return
        _state.update { it.copy(submitting = true, error = null) }
        viewModelScope.launch {
            val result = catalog.createReview(
                productId,
                ReviewCreateRequest(
                    rating = current.rating,
                    text = current.text.trim(),
                    tags = current.selectedTags.toList(),
                    orderItemId = orderItemId,
                ),
            )
            _state.update {
                when (result) {
                    is Outcome.Success -> it.copy(submitting = false, done = true)
                    is Outcome.Failure -> it.copy(submitting = false, error = result.message)
                }
            }
        }
    }
}
