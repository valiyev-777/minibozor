package uz.minibozor.core.util

import android.content.Context
import android.content.res.Configuration
import android.content.res.Resources
import androidx.annotation.StringRes
import java.util.Locale

/**
 * String resources for code that runs outside a composable — view models,
 * repositories, the error mapping in [Outcome].
 *
 * It resolves against a context built for [AppLocale.current] rather than the
 * application context's own resources: after a language switch the application
 * context can still carry the previous configuration, which would leave toasts
 * and error messages a language behind the screen they appear on.
 *
 * A plain object rather than an injected dependency because `apiCall` is a
 * top-level function used at 77 call sites; threading a context through all of
 * them would cost more than it buys.
 */
object AppStrings {

    private lateinit var appContext: Context

    @Volatile private var cached: Resources? = null
    @Volatile private var cachedTag: String? = null

    /** Called once from [uz.minibozor.MiniBozorApp]. */
    fun init(context: Context) {
        appContext = context.applicationContext
    }

    operator fun get(@StringRes id: Int): String = resources().getString(id)

    operator fun get(@StringRes id: Int, vararg args: Any): String =
        resources().getString(id, *args)

    private fun resources(): Resources {
        val tag = AppLocale.current()
        cached?.let { if (cachedTag == tag) return it }
        val config = Configuration(appContext.resources.configuration)
        config.setLocale(Locale.forLanguageTag(tag))
        return appContext.createConfigurationContext(config).resources.also {
            cached = it
            cachedTag = tag
        }
    }
}
