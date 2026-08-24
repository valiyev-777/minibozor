package uz.minibozor.ui.common

import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import uz.minibozor.core.design.component.MbErrorState
import uz.minibozor.core.design.component.MbLoading

/** The three states every data-backed screen can be in. */
sealed interface UiState<out T> {
    data object Loading : UiState<Nothing>
    data class Error(val message: String) : UiState<Nothing>
    data class Ready<T>(val data: T) : UiState<T>
}

val <T> UiState<T>.dataOrNull: T? get() = (this as? UiState.Ready)?.data

/** Renders loading and error uniformly so screens only describe the happy path. */
@Composable
fun <T> UiStateContent(
    state: UiState<T>,
    onRetry: () -> Unit,
    modifier: Modifier = Modifier,
    content: @Composable (T) -> Unit,
) {
    when (state) {
        is UiState.Loading -> MbLoading(modifier)
        is UiState.Error -> MbErrorState(state.message, onRetry, modifier)
        is UiState.Ready -> content(state.data)
    }
}
