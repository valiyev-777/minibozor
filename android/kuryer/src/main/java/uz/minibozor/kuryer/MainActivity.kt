package uz.minibozor.kuryer

import android.annotation.SuppressLint
import android.os.Bundle
import android.view.View
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.TextView
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AppCompatActivity

/**
 * One screen: the web app, full height, with the shop's own chrome.
 *
 * Deliberately not a second implementation of the courier's screens. What the
 * activity owns is the three things a browser tab gets wrong for somebody
 * working on a doorstep — the back key moving through the app's own history
 * rather than leaving it, a failure that says what to do instead of a browser
 * error page, and a session that survives being backgrounded.
 */
class MainActivity : AppCompatActivity() {

    private lateinit var web: WebView
    private lateinit var broken: View

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(state: Bundle?) {
        super.onCreate(state)

        web = WebView(this).apply {
            settings.javaScriptEnabled = true
            // The session lives in `localStorage` (`mb.access`/`mb.refresh`),
            // so without this the courier signs in on every launch.
            settings.domStorageEnabled = true
            settings.mediaPlaybackRequiresUserGesture = false
            settings.useWideViewPort = true
            settings.loadWithOverviewMode = true
            addJavascriptInterface(Bridge(), "Kuryer")
            webViewClient = object : WebViewClient() {
                override fun onReceivedError(
                    view: WebView,
                    request: WebResourceRequest,
                    error: WebResourceError,
                ) {
                    // Only the page itself: a failed image must not replace a
                    // working screen with the offline panel.
                    if (request.isForMainFrame) show(broken)
                }

                override fun onPageFinished(view: WebView, url: String) {
                    if (broken.visibility != View.VISIBLE) show(web)
                    watchTheme(view)
                }
            }
        }

        broken = offlinePanel()

        setContentView(
            FrameLayout(this).apply {
                addView(web, matchParent())
                addView(broken, matchParent())
            }
        )

        show(web)
        web.loadUrl(BuildConfig.HOME_URL)

        // The back key walks the web app's own history first. Leaving the app
        // on the first press is what makes a WebView feel like a browser tab.
        onBackPressedDispatcher.addCallback(
            this,
            object : OnBackPressedCallback(true) {
                override fun handleOnBackPressed() {
                    if (web.canGoBack()) web.goBack() else finish()
                }
            },
        )
    }

    /** Keeps the signed-in page across a rotation or a trip to the camera. */
    override fun onSaveInstanceState(out: Bundle) {
        super.onSaveInstanceState(out)
        web.saveState(out)
    }

    override fun onRestoreInstanceState(state: Bundle) {
        super.onRestoreInstanceState(state)
        web.restoreState(state)
    }

    /**
     * The strip above the page takes the page's own colour.
     *
     * Two theme engines were deciding separately and disagreeing: Android
     * resolved the activity's DayNight resources, while the WebView resolved
     * `prefers-color-scheme` for the page — which produced a white status bar
     * sitting on top of a dark app. The page is the one that knows, and it
     * already publishes the answer as `<meta name="theme-color">`, which it
     * rewrites whenever the theme changes. So: read that, and watch it.
     */
    private fun watchTheme(view: WebView) {
        view.evaluateJavascript(
            """
            (function () {
              var meta = document.querySelector('meta[name="theme-color"]');
              if (!meta || window.__mbThemeWatch) return meta && meta.content;
              window.__mbThemeWatch = true;
              new MutationObserver(function () {
                Kuryer.onThemeColour(meta.content);
              }).observe(meta, { attributes: true, attributeFilter: ['content'] });
              return meta.content;
            })();
            """.trimIndent(),
        ) { value -> paintChrome(value?.trim('"', ' ')) }
    }

    /** Called by the page's own observer when the theme changes under it. */
    @Suppress("unused")
    inner class Bridge {
        @android.webkit.JavascriptInterface
        fun onThemeColour(colour: String) = runOnUiThread { paintChrome(colour) }
    }

    private fun paintChrome(colour: String?) {
        val painted = runCatching { android.graphics.Color.parseColor(colour) }.getOrNull()
            ?: return
        window.statusBarColor = painted
        window.navigationBarColor = painted
        // Glyph colour follows the luminance of what is behind it, so this
        // keeps working for any palette the web app grows later.
        val light = androidx.core.graphics.ColorUtils.calculateLuminance(painted) > 0.5
        androidx.core.view.WindowInsetsControllerCompat(window, window.decorView).apply {
            isAppearanceLightStatusBars = light
            isAppearanceLightNavigationBars = light
        }
    }

    private fun show(one: View) {
        web.visibility = if (one === web) View.VISIBLE else View.GONE
        broken.visibility = if (one === broken) View.VISIBLE else View.GONE
    }

    /**
     * What a courier sees when the server is not there — the shop's wifi, or
     * the server simply off. A browser's own error page names a URL nobody
     * typed and offers nothing to press.
     */
    private fun offlinePanel(): View =
        LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = android.view.Gravity.CENTER
            setPadding(48, 48, 48, 48)
            addView(TextView(context).apply {
                text = getString(R.string.offline_title)
                textSize = 20f
            })
            addView(TextView(context).apply {
                text = getString(R.string.offline_body)
                textSize = 15f
                setPadding(0, 16, 0, 24)
            })
            addView(TextView(context).apply {
                text = "${getString(R.string.address)}: ${BuildConfig.HOME_URL}"
                textSize = 13f
                setPadding(0, 0, 0, 24)
            })
            addView(Button(context).apply {
                text = getString(R.string.retry)
                setOnClickListener {
                    show(web)
                    web.loadUrl(BuildConfig.HOME_URL)
                }
            })
        }

    private fun matchParent() = FrameLayout.LayoutParams(
        FrameLayout.LayoutParams.MATCH_PARENT,
        FrameLayout.LayoutParams.MATCH_PARENT,
    )
}
