package uz.minibozor.navigation

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
import uz.minibozor.ui.cart.CartBadgeViewModel

private val TABS = listOf(
    MbTab(Routes.HOME, "home", "Bosh sahifa"),
    MbTab(Routes.CATALOG, "grid", "Katalog"),
    MbTab(Routes.CART, "cart", "Savat"),
    MbTab(Routes.PROFILE, "user", "Profil"),
)

/**
 * Wraps the four tab destinations with the floating bar from the design. The
 * cart badge reads the shared cart state, so it updates from anywhere.
 */
@Composable
fun MainScaffold(
    currentRoute: String?,
    onSelectTab: (String) -> Unit,
    content: @Composable () -> Unit,
) {
    val badgeViewModel: CartBadgeViewModel = hiltViewModel()
    val badge by badgeViewModel.count.collectAsStateWithLifecycle()

    Box(Modifier.fillMaxSize()) {
        content()
        MbTabBar(
            tabs = TABS.map { if (it.route == Routes.CART) it.copy(badge = badge) else it },
            currentRoute = currentRoute,
            onSelect = { onSelectTab(it.route) },
            modifier = Modifier.align(Alignment.BottomCenter),
        )
    }
}

val TabRoutes: List<String> = TABS.map { it.route }
