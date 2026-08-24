package uz.minibozor.core.design.component

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import uz.minibozor.core.design.MbText
import uz.minibozor.core.design.MbTheme
import uz.minibozor.core.design.icon.MbIcon

data class MbTab(val route: String, val glyph: String, val label: String, val badge: Int = 0)

/**
 * The floating bottom bar from the design: a rounded translucent slab inset from
 * the screen edges, with a tinted pill behind the active item.
 *
 * Compose cannot blur what is behind a composable on all supported versions, so
 * this uses a high-opacity white rather than a live backdrop blur — visually the
 * closest honest match.
 */
@Composable
fun MbTabBar(
    tabs: List<MbTab>,
    currentRoute: String?,
    onSelect: (MbTab) -> Unit,
    modifier: Modifier = Modifier,
) {
    Box(
        modifier
            .fillMaxWidth()
            .windowInsetsPadding(WindowInsets.navigationBars)
            .padding(horizontal = MbTheme.dimens.tabBarInset, vertical = 12.dp)
    ) {
        Row(
            Modifier
                .fillMaxWidth()
                .shadow(18.dp, MbTheme.shapes.tabBar, clip = false)
                .clip(MbTheme.shapes.tabBar)
                .background(Color.White.copy(alpha = 0.94f))
                .border(1.dp, Color.White.copy(alpha = 0.8f), MbTheme.shapes.tabBar)
                .padding(horizontal = 6.dp, vertical = 8.dp),
            horizontalArrangement = Arrangement.SpaceEvenly,
        ) {
            tabs.forEach { tab ->
                TabItem(
                    tab = tab,
                    selected = currentRoute == tab.route,
                    onClick = { onSelect(tab) },
                    modifier = Modifier.weight(1f),
                )
            }
        }
    }
}

@Composable
private fun TabItem(
    tab: MbTab,
    selected: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val tint = if (selected) MbTheme.colors.accent else MbTheme.colors.icon
    Box(modifier, contentAlignment = Alignment.TopCenter) {
        Column(
            Modifier
                .clip(RoundedCornerShape(17.dp))
                .background(
                    if (selected) MbTheme.colors.ink.copy(alpha = 0.05f) else Color.Transparent
                )
                .clickable(onClick = onClick)
                .padding(vertical = 6.dp)
                .fillMaxWidth(),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            MbIcon(tab.glyph, size = 20.dp, tint = tint, strokeWidth = 1.7f)
            MbText(tab.label, MbTheme.type.micro, tint, maxLines = 1)
        }
        if (tab.badge > 0) {
            Box(
                Modifier
                    .padding(start = 22.dp, top = 2.dp)
                    .defaultMinSize(minWidth = 15.dp)
                    .height(15.dp)
                    .clip(CircleShape)
                    .background(MbTheme.colors.danger)
                    .padding(horizontal = 4.dp),
                contentAlignment = Alignment.Center,
            ) {
                MbText(
                    if (tab.badge > 99) "99+" else tab.badge.toString(),
                    MbTheme.type.micro,
                    Color.White,
                )
            }
        }
    }
}

@Composable
fun MbTabBarSpacer() = Spacer(Modifier.size(MbTheme.dimens.tabBarHeight + 26.dp))
