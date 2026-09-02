package uz.minibozor.ui.settings

import uz.minibozor.core.util.AppStrings
import uz.minibozor.R
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import uz.minibozor.core.util.AppLocale
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
import uz.minibozor.data.local.AppPrefs
import uz.minibozor.data.repository.ProfileRepository
import javax.inject.Inject

data class SettingsState(
    val settings: SettingsDto? = null,
    val prefs: NotificationPrefsDto? = null,
    val languages: List<Map<String, String>> = emptyList(),
    /** The language actually in force on this device, not the account's copy. */
    val language: String = AppLocale.DEFAULT,
    /** The dark-mode flag this device is actually themed from. */
    val nightMode: Boolean = false,
    val hasPin: Boolean = false,
    val biometrics: Boolean = false,
)

/** Screens 37–40. */
@HiltViewModel
class SettingsViewModel @Inject constructor(
    private val profile: ProfileRepository,
    private val content: ContentRepository,
    private val prefs: AppPrefs,
) : ViewModel() {

    private val _state = MutableStateFlow(SettingsState())
    val state = _state.asStateFlow()

    init {
        _state.update { it.copy(language = AppLocale.current()) }
        // The device's own flag, watched rather than read once.
        //
        // The switch used to show the account's copy, which is not what themes
        // the app — that is the local one. The two can disagree the moment a
        // customer signs in on a second phone, or the round trip fails, and
        // then the row said "off" over a dark app and turning it on appeared to
        // do nothing. The account's copy is still written, so the other phone
        // learns about it; it just no longer has a vote on what this switch
        // says.
        viewModelScope.launch {
            prefs.nightMode.collect { enabled ->
                _state.update { it.copy(nightMode = enabled) }
            }
        }
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

    /**
     * Applied on the device first, then mirrored to the account. The device is
     * what the user is looking at; the round trip only keeps other devices in
     * step. Changing the locale recreates this activity, so the state update
     * is mostly for the frame before that happens.
     */
    fun setLanguage(code: String) {
        _state.update { it.copy(language = code) }
        AppLocale.apply(code)
        update(SettingsRequest(language = code))
    }

    fun setLocation(enabled: Boolean) = update(SettingsRequest(locationEnabled = enabled))

    /**
     * Written locally as well as to the account: the theme has to react on this
     * device immediately, without waiting for a round trip.
     */
    fun setNightMode(enabled: Boolean) {
        viewModelScope.launch { prefs.setNightMode(enabled) }
        update(SettingsRequest(nightMode = enabled))
    }

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
                it.copy(step = 1, first = "", confirm = "", error = AppStrings[R.string.kodlar_mos_kelmadi])
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
