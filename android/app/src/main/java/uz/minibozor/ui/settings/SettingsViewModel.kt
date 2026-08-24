package uz.minibozor.ui.settings

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import uz.minibozor.core.util.Outcome
import uz.minibozor.data.remote.dto.FaqDto
import uz.minibozor.data.remote.dto.LegalDocDto
import uz.minibozor.data.remote.dto.LegalDocFullDto
import uz.minibozor.data.remote.dto.NotificationPrefsDto
import uz.minibozor.data.remote.dto.NotificationPrefsRequest
import uz.minibozor.data.remote.dto.SettingsDto
import uz.minibozor.data.remote.dto.SettingsRequest
import uz.minibozor.data.repository.AuthRepository
import uz.minibozor.data.repository.ContentRepository
import uz.minibozor.data.repository.ProfileRepository
import javax.inject.Inject

data class SettingsState(
    val settings: SettingsDto? = null,
    val prefs: NotificationPrefsDto? = null,
    val languages: List<Map<String, String>> = emptyList(),
    val hasPin: Boolean = false,
    val biometrics: Boolean = false,
)

/** Screens 37–40. */
@HiltViewModel
class SettingsViewModel @Inject constructor(
    private val profile: ProfileRepository,
    private val content: ContentRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(SettingsState())
    val state = _state.asStateFlow()

    init {
        load()
    }

    fun load() {
        viewModelScope.launch {
            (profile.settings() as? Outcome.Success)?.let { r ->
                _state.update { it.copy(settings = r.data) }
            }
            (profile.notificationPrefs() as? Outcome.Success)?.let { r ->
                _state.update { it.copy(prefs = r.data) }
            }
            (profile.me() as? Outcome.Success)?.let { r ->
                _state.update { it.copy(hasPin = r.data.hasPin, biometrics = r.data.biometricsEnabled) }
            }
            (content.languages() as? Outcome.Success)?.let { r ->
                _state.update { it.copy(languages = r.data) }
            }
        }
    }

    fun setLanguage(code: String) = update(SettingsRequest(language = code))

    fun setLocation(enabled: Boolean) = update(SettingsRequest(locationEnabled = enabled))

    fun setNightMode(enabled: Boolean) = update(SettingsRequest(nightMode = enabled))

    fun setBiometrics(enabled: Boolean) {
        viewModelScope.launch {
            (profile.setBiometrics(enabled) as? Outcome.Success)?.let { r ->
                _state.update { it.copy(biometrics = r.data.biometricsEnabled) }
            }
        }
    }

    fun setPref(body: NotificationPrefsRequest) {
        viewModelScope.launch {
            (profile.updateNotificationPrefs(body) as? Outcome.Success)?.let { r ->
                _state.update { it.copy(prefs = r.data) }
            }
        }
    }

    private fun update(body: SettingsRequest) {
        viewModelScope.launch {
            (profile.updateSettings(body) as? Outcome.Success)?.let { r ->
                _state.update { it.copy(settings = r.data) }
            }
        }
    }
}

data class PinState(
    val step: Int = 0,
    val current: String = "",
    val first: String = "",
    val confirm: String = "",
    val error: String? = null,
    val submitting: Boolean = false,
    val done: Boolean = false,
)

/** Screens 41–44: current code → new code → confirm → success. */
@HiltViewModel
class PinViewModel @Inject constructor(
    private val auth: AuthRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(PinState())
    val state = _state.asStateFlow()

    /** [needsCurrent] is false when the user has no PIN yet (screen 42 first). */
    fun start(needsCurrent: Boolean) {
        _state.value = PinState(step = if (needsCurrent) 0 else 1)
    }

    fun onDigits(value: String) {
        _state.update { state ->
            when (state.step) {
                0 -> state.copy(current = value, error = null)
                1 -> state.copy(first = value, error = null)
                else -> state.copy(confirm = value, error = null)
            }
        }
        advance()
    }

    private fun advance() {
        val state = _state.value
        when (state.step) {
            0 -> if (state.current.length == LENGTH) _state.update { it.copy(step = 1) }
            1 -> if (state.first.length == LENGTH) _state.update { it.copy(step = 2) }
            else -> if (state.confirm.length == LENGTH) submit()
        }
    }

    private fun submit() {
        val state = _state.value
        if (state.first != state.confirm) {
            _state.update {
                it.copy(step = 1, first = "", confirm = "", error = "Kodlar mos kelmadi")
            }
            return
        }
        _state.update { it.copy(submitting = true) }
        viewModelScope.launch {
            val result = auth.setPin(state.current.ifBlank { null }, state.first)
            _state.update {
                when (result) {
                    is Outcome.Success -> it.copy(submitting = false, done = true)
                    is Outcome.Failure -> it.copy(
                        submitting = false,
                        step = 0,
                        current = "",
                        first = "",
                        confirm = "",
                        error = result.message,
                    )
                }
            }
        }
    }

    companion object {
        const val LENGTH = 4
    }
}

data class ContentState(
    val faq: List<FaqDto> = emptyList(),
    val support: Map<String, String> = emptyMap(),
    val docs: List<LegalDocDto> = emptyList(),
    val doc: LegalDocFullDto? = null,
)

/** Screens 45 and 46. */
@HiltViewModel
class ContentViewModel @Inject constructor(
    private val repo: ContentRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(ContentState())
    val state = _state.asStateFlow()

    init {
        viewModelScope.launch {
            (repo.faq() as? Outcome.Success)?.let { r -> _state.update { it.copy(faq = r.data) } }
            (repo.support() as? Outcome.Success)?.let { r ->
                _state.update { it.copy(support = r.data) }
            }
            (repo.legalDocs() as? Outcome.Success)?.let { r ->
                _state.update { it.copy(docs = r.data) }
            }
        }
    }

    fun loadDoc(slug: String) {
        viewModelScope.launch {
            (repo.legalDoc(slug) as? Outcome.Success)?.let { r ->
                _state.update { it.copy(doc = r.data) }
            }
        }
    }
}
