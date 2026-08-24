package uz.minibozor.data.local

import android.content.Context
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

private val Context.dataStore by preferencesDataStore("minibozor")

/** Small bits of device-local state: onboarding, city, PIN lock. */
@Singleton
class AppPrefs @Inject constructor(@ApplicationContext private val context: Context) {

    val onboardingSeen: Flow<Boolean> =
        context.dataStore.data.map { it[ONBOARDING_SEEN] ?: false }

    val pinLockEnabled: Flow<Boolean> =
        context.dataStore.data.map { it[PIN_LOCK] ?: false }

    val city: Flow<String> =
        context.dataStore.data.map { it[CITY] ?: "Toshkent" }

    suspend fun setOnboardingSeen() = context.dataStore.edit { it[ONBOARDING_SEEN] = true }

    suspend fun setPinLock(enabled: Boolean) = context.dataStore.edit { it[PIN_LOCK] = enabled }

    suspend fun setCity(city: String) = context.dataStore.edit { it[CITY] = city }

    private companion object {
        val ONBOARDING_SEEN = booleanPreferencesKey("onboarding_seen")
        val PIN_LOCK = booleanPreferencesKey("pin_lock")
        val CITY = stringPreferencesKey("city")
    }
}
