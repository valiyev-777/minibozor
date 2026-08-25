package uz.minibozor

import android.os.Bundle
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.core.view.WindowCompat
import dagger.hilt.android.AndroidEntryPoint
import uz.minibozor.core.design.MiniBozorTheme
import uz.minibozor.data.local.AppPrefs
import uz.minibozor.navigation.MiniBozorNavHost
import javax.inject.Inject

/**
 * AppCompatActivity rather than ComponentActivity: that is what lets
 * AppCompatDelegate apply the per-app language on devices older than
 * Android 13. See [uz.minibozor.core.util.AppLocale].
 */
@AndroidEntryPoint
class MainActivity : AppCompatActivity() {

    @Inject lateinit var prefs: AppPrefs

    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        setContent {
            // "Tungi rejim" forces dark; off means follow the system, which is
            // what the settings row promises.
            val forceDark by prefs.nightMode.collectAsState(initial = false)
            val dark = forceDark || isSystemInDarkTheme()

            // enableEdgeToEdge picks bar icon colours from the system setting,
            // which is wrong whenever the switch overrides it.
            val window = window
            SideEffect {
                WindowCompat.getInsetsController(window, window.decorView).run {
                    isAppearanceLightStatusBars = !dark
                    isAppearanceLightNavigationBars = !dark
                }
            }

            MiniBozorTheme(darkTheme = dark) {
                MiniBozorNavHost()
            }
        }
    }
}
