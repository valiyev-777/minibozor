package uz.minibozor.navigation

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import uz.minibozor.data.local.AppPrefs
import uz.minibozor.data.local.TokenStore
import javax.inject.Inject

/** Decides where the app opens: onboarding, sign-in, or straight to the shop. */
@HiltViewModel
class StartViewModel @Inject constructor(
    private val prefs: AppPrefs,
    private val tokens: TokenStore,
) : ViewModel() {

    private val _destination = MutableStateFlow<String?>(null)
    val destination = _destination.asStateFlow()

    init {
        viewModelScope.launch {
            val seenOnboarding = prefs.onboardingSeen.first()
            // Signed in wins: someone with a session never sees the intro again.
            _destination.value = when {
                tokens.signedIn.value -> Routes.HOME
                !seenOnboarding -> Routes.ONBOARDING
                else -> Routes.LOGIN
            }
        }
    }

    fun markOnboardingSeen() {
        viewModelScope.launch { prefs.setOnboardingSeen() }
    }
}
