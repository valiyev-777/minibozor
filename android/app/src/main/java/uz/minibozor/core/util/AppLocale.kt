package uz.minibozor.core.util

import androidx.appcompat.app.AppCompatDelegate
import androidx.core.os.LocaleListCompat

/**
 * The app's language.
 *
 * AppCompatDelegate owns the choice rather than our own preferences: it
 * persists it across process death, and on Android 13 and up it registers with
 * the system so the language also appears in Settings → Apps → Mini Bozor.
 * Keeping a second copy in DataStore would only give the two something to
 * disagree about.
 */
object AppLocale {

    /** Uzbek lives in res/values, so it is both the default and the fallback. */
    const val DEFAULT = "uz"

    val SUPPORTED = listOf(DEFAULT, "ru", "en")

    /** The active language tag, or [DEFAULT] when the user has never chosen. */
    fun current(): String =
        AppCompatDelegate.getApplicationLocales()[0]
            ?.language
            ?.takeIf { it in SUPPORTED }
            ?: DEFAULT

    /**
     * Switches language. Android recreates the running activities to pick up
     * the new resources, so the screen rebuilds — that is the brief flicker on
     * screen 39, not a bug.
     *
     * Must be called from the main thread.
     */
    fun apply(code: String) {
        val tag = code.takeIf { it in SUPPORTED } ?: DEFAULT
        if (tag == current()) return
        AppCompatDelegate.setApplicationLocales(LocaleListCompat.forLanguageTags(tag))
    }
}
