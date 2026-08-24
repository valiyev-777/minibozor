package uz.minibozor.ui.search

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.FlowPreview
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.debounce
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import uz.minibozor.core.util.Outcome
import uz.minibozor.data.remote.dto.SuggestionDto
import uz.minibozor.data.repository.CatalogRepository
import javax.inject.Inject

data class SearchState(
    val query: String = "",
    val recent: List<String> = emptyList(),
    val popular: List<String> = emptyList(),
    val suggestions: List<SuggestionDto> = emptyList(),
)

@OptIn(FlowPreview::class)
@HiltViewModel
class SearchViewModel @Inject constructor(
    private val catalog: CatalogRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(SearchState())
    val state = _state.asStateFlow()

    private val typed = MutableStateFlow("")

    init {
        loadLanding()
        viewModelScope.launch {
            typed
                .debounce(250)
                .distinctUntilChanged()
                .collect { q ->
                    if (q.length < 2) {
                        _state.update { it.copy(suggestions = emptyList()) }
                    } else {
                        val result = catalog.suggest(q)
                        if (result is Outcome.Success) {
                            _state.update { it.copy(suggestions = result.data) }
                        }
                    }
                }
        }
    }

    fun onQueryChange(value: String) {
        _state.update { it.copy(query = value) }
        typed.value = value
    }

    fun remember(query: String) {
        if (query.isBlank()) return
        viewModelScope.launch {
            catalog.rememberSearch(query)
            loadLanding()
        }
    }

    fun clearHistory() {
        viewModelScope.launch {
            catalog.clearSearchHistory()
            _state.update { it.copy(recent = emptyList()) }
        }
    }

    private fun loadLanding() {
        viewModelScope.launch {
            val result = catalog.searchLanding()
            if (result is Outcome.Success) {
                _state.update { it.copy(recent = result.data.recent, popular = result.data.popular) }
            }
        }
    }
}
