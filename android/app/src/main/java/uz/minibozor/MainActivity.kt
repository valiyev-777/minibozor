package uz.minibozor

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import dagger.hilt.android.AndroidEntryPoint
import uz.minibozor.core.design.MiniBozorTheme
import uz.minibozor.data.local.AppPrefs
import uz.minibozor.navigation.MiniBozorNavHost
import javax.inject.Inject

@AndroidEntryPoint
class MainActivity : ComponentActivity() {

    @Inject lateinit var prefs: AppPrefs

    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        setContent {
            // "Tungi rejim" forces dark; off means follow the system, which is
            // what the settings row promises.
            val forceDark by prefs.nightMode.collectAsState(initial = false)
            MiniBozorTheme(darkTheme = forceDark || isSystemInDarkTheme()) {
                MiniBozorNavHost()
            }
        }
    }
}
