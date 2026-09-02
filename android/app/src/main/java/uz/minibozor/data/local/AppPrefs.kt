package uz.minibozor.data.local

import android.content.Context
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.onEach
import kotlinx.coroutines.runBlocking
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

    /** When on, the app is dark regardless of the system setting. */
    val nightMode: Flow<Boolean> =
        context.dataStore.data.map { it[NIGHT_MODE] ?: false }.onEach { nightCache = it }

    @Volatile private var nightCache: Boolean? = null

    /**
     * The same flag, readable without a coroutine.
     *
     * The theme has to be right on the very first frame, and a Flow cannot
     * answer that: whatever is passed as the initial value of a
     * `collectAsState` is what the app paints until the store has been read off
     * the disk. Guessing "light" there means anyone who keeps the app dark gets
     * a white screen on every cold start and on every rebuild the system hands
     * us — a language change on Android 12 and below is exactly that, which is
     * where it was most visible.
     *
     * So the first read is done up front and blocks, once per process, for as
     * long as it takes to read one small file; every later read comes from the
     * cache [nightMode] keeps warm.
     */
    val nightModeNow: Boolean
        get() = nightCache
            ?: runBlocking { context.dataStore.data.first()[NIGHT_MODE] ?: false }
                .also { nightCache = it }

    val city: Flow<String> =
        context.dataStore.data.map { it[CITY] ?: "Toshkent" }

    suspend fun setOnboardingSeen(seen: Boolean = true) =
        context.dataStore.edit { it[ONBOARDING_SEEN] = seen }

    suspend fun setPinLock(enabled: Boolean) = context.dataStore.edit { it[PIN_LOCK] = enabled }

    suspend fun setCity(city: String) = context.dataStore.edit { it[CITY] = city }

    suspend fun setNightMode(enabled: Boolean) {
        nightCache = enabled
        context.dataStore.edit { it[NIGHT_MODE] = enabled }
    }

    private companion object {
        val ONBOARDING_SEEN = booleanPreferencesKey("onboarding_seen")
        val PIN_LOCK = booleanPreferencesKey("pin_lock")
        val NIGHT_MODE = booleanPreferencesKey("night_mode")
        val CITY = stringPreferencesKey("city")
    }
}
