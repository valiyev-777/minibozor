package uz.minibozor.data.local

import android.content.Context
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Token storage, backed by EncryptedSharedPreferences so the refresh token is
 * not sitting in plaintext on a rooted device.
 *
 * Reads are synchronous on purpose: the OkHttp interceptor and authenticator run
 * on network threads and cannot suspend.
 */
@Singleton
class TokenStore @Inject constructor(@ApplicationContext context: Context) {

    private val prefs = EncryptedSharedPreferences.create(
        context,
        "minibozor.tokens",
        MasterKey.Builder(context).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build(),
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
    )

    private val _signedIn = MutableStateFlow(prefs.contains(KEY_ACCESS))
    val signedIn: StateFlow<Boolean> = _signedIn.asStateFlow()

    val accessToken: String? get() = prefs.getString(KEY_ACCESS, null)
    val refreshToken: String? get() = prefs.getString(KEY_REFRESH, null)

    fun save(access: String, refresh: String) {
        prefs.edit().putString(KEY_ACCESS, access).putString(KEY_REFRESH, refresh).apply()
        _signedIn.value = true
    }

    fun updateAccess(access: String) {
        prefs.edit().putString(KEY_ACCESS, access).apply()
    }

    fun clear() {
        prefs.edit().clear().apply()
        _signedIn.value = false
    }

    private companion object {
        const val KEY_ACCESS = "access"
        const val KEY_REFRESH = "refresh"
    }
}
