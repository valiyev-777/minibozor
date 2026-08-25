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
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import uz.minibozor.core.design.GlassBackdrop
import uz.minibozor.core.design.MbText
import uz.minibozor.core.design.MbTheme
import uz.minibozor.core.design.icon.MbIcon
import uz.minibozor.core.design.liquidGlass

data class MbTab(val route: String, val glyph: String, val label: String, val badge: Int = 0)

/**
 * The floating bottom bar, iOS-style: a full pill of live "liquid glass" that
 * blurs whatever scrolls beneath it (see [uz.minibozor.core.design.liquidGlass]),
 * with a soft round lens behind the active item. Without a [backdrop] — or on
 * devices without RenderEffect — it falls back to the translucent slab.
 */
@Composable
fun MbTabBar(
    tabs: List<MbTab>,
    currentRoute: String?,
    onSelect: (MbTab) -> Unit,
    modifier: Modifier = Modifier,
    backdrop: GlassBackdrop? = null,
) {
    // Sit the design's 16 dp above the bottom, but never under the system
    // navigation — on a three-button device that inset is what clears the keys.
    val navBottom = WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding()
    val pill = MbTheme.shapes.chip

    Box(
        modifier
            .fillMaxWidth()
            .padding(horizontal = MbTheme.dimens.tabBarInset)
            .padding(top = 12.dp, bottom = maxOf(navBottom, MbTheme.dimens.tabBarBottom))
    ) {
        Row(
            Modifier
                .fillMaxWidth()
                .shadow(22.dp, pill, clip = false)
                .clip(pill)
                .let { row ->
                    if (backdrop != null) {
                        row.liquidGlass(
                            backdrop = backdrop,
                            tint = MbTheme.colors.glass.copy(alpha = 0.62f),
                            fallback = MbTheme.colors.glass,
                        )
                    } else {
                        row.background(MbTheme.colors.glass)
                    }
                }
                .border(1.dp, MbTheme.colors.border, pill)
                .padding(horizontal = 10.dp, vertical = 9.dp),
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
                .clip(MbTheme.shapes.chip)
                .background(
                    if (selected) MbTheme.colors.accent.copy(alpha = 0.12f) else Color.Transparent
                )
                .clickable(onClick = onClick)
                .padding(vertical = 8.dp)
                .fillMaxWidth(),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(5.dp),
        ) {
            MbIcon(tab.glyph, size = 30.dp, tint = tint, strokeWidth = 1.8f)
            MbText(tab.label, MbTheme.type.label, tint, maxLines = 1)
        }
        if (tab.badge > 0) {
            Box(
                Modifier
                    .padding(start = 26.dp, top = 2.dp)
                    .defaultMinSize(minWidth = 16.dp)
                    .height(16.dp)
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
