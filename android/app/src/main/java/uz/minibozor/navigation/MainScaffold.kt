package uz.minibozor.navigation

import androidx.compose.ui.res.stringResource
import uz.minibozor.R
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.hilt.navigation.compose.hiltViewModel
import uz.minibozor.core.design.component.MbTab
import uz.minibozor.core.design.component.MbTabBar
import uz.minibozor.core.design.MbLiveGlass
import uz.minibozor.core.design.glassSource
import uz.minibozor.core.design.rememberGlassBackdrop
import uz.minibozor.ui.cart.CartBadgeViewModel

private val TAB_LABELS = listOf(
    Routes.HOME to R.string.tab_home,
    Routes.CATALOG to R.string.tab_catalog,
    Routes.CART to R.string.tab_cart,
    Routes.PROFILE to R.string.tab_profile,
)

private val TAB_GLYPHS = mapOf(
    Routes.HOME to "home",
    Routes.CATALOG to "grid",
    Routes.CART to "cart",
    Routes.PROFILE to "user",
)

/** Built inside the composition so the labels follow the app language. */
@Composable
private fun tabs(badge: Int): List<MbTab> = TAB_LABELS.map { (route, label) ->
    MbTab(
        route = route,
        glyph = TAB_GLYPHS.getValue(route),
        label = stringResource(label),
        badge = if (route == Routes.CART) badge else 0,
    )
}

/**
 * Wraps the tab destinations with the floating glass bar. With [MbLiveGlass] on,
 * the screen's content is recorded as the bar's backdrop, which is what the bar
 * blurs; off, neither the recording nor the blur happens. The cart badge reads
 * the shared cart state, so it updates from anywhere.
 */
@Composable
fun MainScaffold(
    currentRoute: String?,
    onSelectTab: (String) -> Unit,
    content: @Composable () -> Unit,
) {
    val badgeViewModel: CartBadgeViewModel = hiltViewModel()
    val badge by badgeViewModel.count.collectAsStateWithLifecycle()
    // Null unless the live blur is on: without a backdrop the bar draws its
    // slab, and the screen underneath is not recorded at all. See [MbLiveGlass].
    val backdrop = if (MbLiveGlass) rememberGlassBackdrop() else null

    Box(Modifier.fillMaxSize()) {
        Box(
            Modifier
                .fillMaxSize()
                .let { if (backdrop != null) it.glassSource(backdrop) else it }
        ) {
            content()
        }
        MbTabBar(
            tabs = tabs(badge),
            currentRoute = currentRoute,
            onSelect = { onSelectTab(it.route) },
            modifier = Modifier.align(Alignment.BottomCenter),
            backdrop = backdrop,
        )
    }
}

val TabRoutes: List<String> = TAB_LABELS.map { it.first }
