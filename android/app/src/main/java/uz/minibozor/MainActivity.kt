package uz.minibozor

import android.graphics.drawable.ColorDrawable
import android.os.Bundle
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalConfiguration
import androidx.core.view.WindowCompat
import dagger.hilt.android.AndroidEntryPoint
import uz.minibozor.core.design.MbColors
import uz.minibozor.core.design.MbTheme
import uz.minibozor.core.design.MiniBozorTheme
import uz.minibozor.data.local.AppPrefs
import uz.minibozor.navigation.LocaleRestart
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

        // Read before the first frame is composed rather than awaited as a
        // Flow. Starting the tree at "light" and correcting it a frame later is
        // a white flash across the whole screen for anyone who keeps the app
        // dark, and it happens on every cold start and every rebuild the
        // system hands us — a language change below Android 13 among them.
        val initialNight = prefs.nightModeNow

        setContent {
            // "Tungi rejim" forces dark; off means follow the system, which is
            // what the settings row promises.
            val forceDark by prefs.nightMode.collectAsState(initial = initialNight)
            val dark = forceDark || isSystemInDarkTheme()

            // enableEdgeToEdge picks bar icon colours from the system setting,
            // which is wrong whenever the switch overrides it.
            //
            // On the theme changing and on nothing else. As a SideEffect this ran
            // after every recomposition of the tree's root, which meant any
            // screen that legitimately wants white icons over a photograph — the
            // product page — had them taken away again the next time anything up
            // here recomposed, leaving the clock invisible on a dark picture.
            val window = window
            LaunchedEffect(dark) {
                WindowCompat.getInsetsController(window, window.decorView).run {
                    isAppearanceLightStatusBars = !dark
                    isAppearanceLightNavigationBars = !dark
                }
            }

            // The window's own ground, painted in the theme's canvas.
            //
            // Android 12 and up hand the window background to the splash screen
            // and clear it once the splash is done — so a window with no frame
            // drawn yet is plain black. That is what a language switch showed:
            // the activity is torn down and rebuilt, and the gap between the
            // two was a black screen. Setting it here means the gap is the
            // colour the app is about to draw anyway, and it follows the theme
            // rather than the resource qualifier, which answers to the system's
            // dark mode instead of our own switch.
            val canvasArgb = (if (dark) MbColors.dark() else MbColors()).canvas.toArgb()
            SideEffect { window.setBackgroundDrawable(ColorDrawable(canvasArgb)) }

            MiniBozorTheme(darkTheme = dark) {
                LanguageSwitchEntrance {
                    MiniBozorNavHost()
                }
            }
        }
    }
}

/**
 * Builds the app fresh in the new language, and slides it in from the side.
 *
 * The activity itself is no longer torn down for a language change — that is
 * what used to put a black screen between the two languages — but the app tree
 * inside it is, and deliberately: half the text on a product page comes from the
 * server, translated there against the language the request asked for. Keeping
 * the tree alive kept those strings, so a Russian page carried an Uzbek product
 * name and an Uzbek delivery note. Keying the whole graph on the locale gives
 * every screen a new view model, and every view model fetches again in the
 * language now being spoken.
 *
 * What the customer sees is the app arriving from the right, the way a pushed
 * screen arrives — a page being turned into the new language rather than a
 * flicker. The key is the configuration's own locale, so this happens when the
 * language really changes and on nothing else: not on a rotation, not on a theme
 * switch, and not on the first frame.
 */
@Composable
private fun LanguageSwitchEntrance(content: @Composable () -> Unit) {
    val tag = LocalConfiguration.current.locales[0].toLanguageTag()
    var shown by remember { mutableStateOf(tag) }
    val entrance = remember { Animatable(1f) }

    LaunchedEffect(tag) {
        if (tag != shown) {
            shown = tag
            // The tree below is about to be discarded, navigation and all.
            // This is what lets the screen the switch was made on come back.
            LocaleRestart.arm()
            entrance.snapTo(0f)
            entrance.animateTo(1f, tween(durationMillis = 340, easing = FastOutSlowInEasing))
        }
    }

    Box(
        Modifier
            .fillMaxSize()
            // Opaque, so the page arriving never shows the window through it.
            .background(MbTheme.colors.canvas)
            .graphicsLayer {
                val progress = entrance.value
                translationX = (1f - progress) * size.width * 0.35f
                alpha = progress
            }
    ) {
        key(tag) { content() }
    }
}
