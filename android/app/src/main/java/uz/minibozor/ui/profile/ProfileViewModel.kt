package uz.minibozor.ui.profile

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import uz.minibozor.core.util.Outcome
import uz.minibozor.data.remote.dto.ProfileOverviewDto
import uz.minibozor.data.remote.dto.UserUpdateRequest
import uz.minibozor.data.repository.AuthRepository
import uz.minibozor.data.repository.ProfileRepository
import javax.inject.Inject

data class ProfileState(
    val loading: Boolean = true,
    val overview: ProfileOverviewDto? = null,
    val error: String? = null,
    val signedOut: Boolean = false,
    val saving: Boolean = false,
    val saved: Boolean = false,
)

/** Screens 30 and 31. */
@HiltViewModel
class ProfileViewModel @Inject constructor(
    private val profile: ProfileRepository,
    private val auth: AuthRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(ProfileState())
    val state = _state.asStateFlow()

    init {
        load()
    }

    fun load() {
        viewModelScope.launch {
            _state.update { it.copy(loading = true, error = null) }
            _state.update {
                when (val result = profile.overview()) {
                    is Outcome.Success -> it.copy(loading = false, overview = result.data)
                    is Outcome.Failure -> it.copy(loading = false, error = result.message)
                }
            }
        }
    }

    fun save(fullName: String, email: String, birthDate: String?, gender: String?) {
        _state.update { it.copy(saving = true, saved = false) }
        viewModelScope.launch {
            val result = profile.updateMe(
                UserUpdateRequest(
                    fullName = fullName.trim(),
                    email = email.trim().ifBlank { null },
                    birthDate = birthDate,
                    gender = gender,
                )
            )
            _state.update {
                when (result) {
                    is Outcome.Success -> it.copy(
                        saving = false,
                        saved = true,
                        overview = it.overview?.copy(user = result.data),
                    )
                    is Outcome.Failure -> it.copy(saving = false, error = result.message)
                }
            }
        }
    }

    fun signOut() {
        viewModelScope.launch {
            auth.logout()
            _state.update { it.copy(signedOut = true) }
        }
    }
}
