package uz.minibozor.ui.auth

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import uz.minibozor.core.util.Outcome
import uz.minibozor.core.util.toApiPhone
import uz.minibozor.data.repository.AuthRepository
import javax.inject.Inject

data class AuthState(
    val phoneDigits: String = "",
    val code: String = "",
    val sending: Boolean = false,
    val verifying: Boolean = false,
    val error: String? = null,
    /** Dev builds echo the SMS code back so the flow works without a gateway. */
    val devCode: String? = null,
    val secondsLeft: Int = 0,
    val codeSent: Boolean = false,
    val signedIn: Boolean = false,
    val isNewUser: Boolean = false,
) {
    val phoneValid: Boolean get() = phoneDigits.length == 9
    val codeValid: Boolean get() = code.length == CODE_LENGTH
    val canResend: Boolean get() = secondsLeft == 0

    companion object {
        const val CODE_LENGTH = 6
    }
}

@HiltViewModel
class AuthViewModel @Inject constructor(
    private val repo: AuthRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(AuthState())
    val state: StateFlow<AuthState> = _state.asStateFlow()

    private var ticker: Job? = null

    fun onPhoneChange(raw: String) {
        val digits = raw.filter(Char::isDigit).take(9)
        _state.update { it.copy(phoneDigits = digits, error = null) }
    }

    fun onCodeChange(code: String) {
        _state.update { it.copy(code = code, error = null) }
        if (code.length == AuthState.CODE_LENGTH) verify()
    }

    fun sendCode() {
        val phone = _state.value.phoneDigits
        if (phone.length != 9 || _state.value.sending) return

        _state.update { it.copy(sending = true, error = null) }
        viewModelScope.launch {
            when (val result = repo.requestOtp(phone.toApiPhone())) {
                is Outcome.Success -> {
                    _state.update {
                        it.copy(
                            sending = false,
                            codeSent = true,
                            devCode = result.data.devCode,
                            code = "",
                        )
                    }
                    startTimer(result.data.resendAfter)
                }
                is Outcome.Failure ->
                    _state.update { it.copy(sending = false, error = result.message) }
            }
        }
    }

    fun verify() {
        val current = _state.value
        if (!current.codeValid || current.verifying) return

        _state.update { it.copy(verifying = true, error = null) }
        viewModelScope.launch {
            when (val result = repo.verifyOtp(current.phoneDigits.toApiPhone(), current.code)) {
                is Outcome.Success ->
                    _state.update {
                        it.copy(verifying = false, signedIn = true, isNewUser = result.data)
                    }
                is Outcome.Failure ->
                    _state.update { it.copy(verifying = false, error = result.message, code = "") }
            }
        }
    }

    fun consumeSignIn() {
        _state.update { it.copy(signedIn = false) }
    }

    private fun startTimer(seconds: Int) {
        ticker?.cancel()
        ticker = viewModelScope.launch {
            for (remaining in seconds downTo 0) {
                _state.update { it.copy(secondsLeft = remaining) }
                delay(1_000)
            }
        }
    }

    override fun onCleared() {
        ticker?.cancel()
    }
}
