package uz.minibozor.core.util

import androidx.appcompat.app.AppCompatDelegate
import androidx.core.os.LocaleListCompat
import java.util.Locale

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

    /**
     * The language the app is actually speaking.
     *
     * An explicit choice on screen 39 wins. Failing that it is whatever
     * Android resolved the resources against — on a phone set to English the
     * screens come back in English even though nobody picked a language, and
     * answering "uz" here put Uzbek toasts under English headings and asked
     * the server for Uzbek too.
     */
    fun current(): String {
        val chosen = AppCompatDelegate.getApplicationLocales()[0]?.language
        if (chosen != null && chosen in SUPPORTED) return chosen
        val system = Locale.getDefault().language
        return if (system in SUPPORTED) system else DEFAULT
    }

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
