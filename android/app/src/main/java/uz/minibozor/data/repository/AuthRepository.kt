package uz.minibozor.data.repository

import kotlinx.coroutines.flow.StateFlow
import uz.minibozor.core.util.Outcome
import uz.minibozor.core.util.apiCall
import uz.minibozor.data.local.AppPrefs
import uz.minibozor.data.local.TokenStore
import uz.minibozor.data.remote.MiniBozorApi
import uz.minibozor.data.remote.dto.OtpRequestedDto
import uz.minibozor.data.remote.dto.OtpVerifyRequest
import uz.minibozor.data.remote.dto.PhoneRequest
import uz.minibozor.data.remote.dto.PinChangeRequest
import uz.minibozor.data.remote.dto.PinRequest
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AuthRepository @Inject constructor(
    private val api: MiniBozorApi,
    private val tokens: TokenStore,
    private val prefs: AppPrefs,
) {
    val signedIn: StateFlow<Boolean> = tokens.signedIn

    suspend fun requestOtp(phone: String): Outcome<OtpRequestedDto> =
        apiCall { api.requestOtp(PhoneRequest(phone)) }

    /** @return true when this was a brand-new account, so we can ask for a name. */
    suspend fun verifyOtp(phone: String, code: String): Outcome<Boolean> =
        apiCall { api.verifyOtp(OtpVerifyRequest(phone, code)) }.let { outcome ->
            when (outcome) {
                is Outcome.Success -> {
                    tokens.save(outcome.data.accessToken, outcome.data.refreshToken)
                    Outcome.Success(outcome.data.isNewUser)
                }
                is Outcome.Failure -> outcome
            }
        }

    /**
     * Signs out locally whatever the server says — a failed revoke must not
     * leave the user stuck in a session they asked to end.
     */
    suspend fun logout(): Outcome<Unit> {
        apiCall { api.logout() }
        tokens.clear()
        // Signing out returns the app to its first-run state, so the next person
        // to pick up the phone gets the introduction again.
        prefs.setOnboardingSeen(false)
        return Outcome.Success(Unit)
    }

    suspend fun setPin(currentPin: String?, newPin: String): Outcome<Unit> =
        when (val r = apiCall { api.setPin(PinChangeRequest(currentPin, newPin)) }) {
            is Outcome.Success -> Outcome.Success(Unit)
            is Outcome.Failure -> r
        }

    suspend fun verifyPin(pin: String): Outcome<Unit> =
        when (val r = apiCall { api.verifyPin(PinRequest(pin)) }) {
            is Outcome.Success -> Outcome.Success(Unit)
            is Outcome.Failure -> r
        }

    suspend fun removePin(pin: String): Outcome<Unit> =
        when (val r = apiCall { api.removePin(PinRequest(pin)) }) {
            is Outcome.Success -> Outcome.Success(Unit)
            is Outcome.Failure -> r
        }
}
