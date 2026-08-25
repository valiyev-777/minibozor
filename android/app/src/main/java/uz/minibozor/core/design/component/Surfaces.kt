package uz.minibozor.core.design.component

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Scaffold
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import uz.minibozor.core.design.MbText
import uz.minibozor.core.design.MbTheme
import uz.minibozor.core.design.icon.MbIcon

/**
 * The page shell every screen sits in: canvas background, status-bar inset, and
 * an optional pinned footer for the primary action.
 */
@Composable
fun MbScreen(
    modifier: Modifier = Modifier,
    background: Color = MbTheme.colors.canvas,
    topBar: @Composable () -> Unit = {},
    bottomBar: @Composable () -> Unit = {},
    content: @Composable (androidx.compose.foundation.layout.PaddingValues) -> Unit,
) {
    Scaffold(
        modifier = modifier.fillMaxSize(),
        containerColor = background,
        topBar = topBar,
        bottomBar = bottomBar,
        contentWindowInsets = WindowInsets.statusBars,
        content = content,
    )
}

/**
 * The header used across the inner screens: a circular back button, a centred
 * title, and room for one trailing action.
 */
@Composable
fun MbTopBar(
    title: String,
    onBack: (() -> Unit)? = null,
    subtitle: String? = null,
    background: Color = MbTheme.colors.surface,
    action: @Composable (() -> Unit)? = null,
) {
    Column(
        Modifier
            .fillMaxWidth()
            .background(background)
            .windowInsetsPadding(WindowInsets.statusBars)
            .padding(horizontal = 14.dp, vertical = 10.dp)
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            if (onBack != null) {
                CircleIconButton(glyph = "arrow-left", onClick = onBack)
            } else {
                Spacer(Modifier.size(36.dp))
            }
            Column(
                Modifier.weight(1f),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                MbText(title, MbTheme.type.title3, maxLines = 1)
                if (subtitle != null) {
                    MbText(subtitle, MbTheme.type.meta, MbTheme.colors.textQuaternary, maxLines = 1)
                }
            }
            Row(
                Modifier.defaultMinSize(minWidth = 36.dp, minHeight = 36.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(14.dp),
            ) {
                action?.invoke()
            }
        }
    }
}

@Composable
fun CircleIconButton(
    glyph: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    size: Dp = 36.dp,
    tint: Color = MbTheme.colors.ink,
    background: Color = MbTheme.colors.fill,
) {
    Box(
        modifier
            .size(size)
            .clip(CircleShape)
            .background(background)
            .clickable(onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        MbIcon(glyph, size = size * 0.5f, tint = tint, strokeWidth = 1.9f)
    }
}

/** The white rounded panel the design groups content into. */
@Composable
fun MbCard(
    modifier: Modifier = Modifier,
    padding: Dp = 16.dp,
    background: Color = MbTheme.colors.surface,
    onClick: (() -> Unit)? = null,
    content: @Composable ColumnScope.() -> Unit,
) {
    Column(
        modifier
            .fillMaxWidth()
            .clip(MbTheme.shapes.card)
            .background(background)
            .let { if (onClick != null) it.clickable(onClick = onClick) else it }
            .padding(padding),
        content = content,
    )
}

@Composable
fun SectionHeader(
    title: String,
    subtitle: String? = null,
    actionLabel: String? = null,
    onAction: (() -> Unit)? = null,
    modifier: Modifier = Modifier,
) {
    Row(
        modifier.fillMaxWidth(),
        verticalAlignment = Alignment.Bottom,
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        MbText(title, MbTheme.type.sectionHead)
        if (subtitle != null) {
            MbText(subtitle, MbTheme.type.meta, MbTheme.colors.icon, maxLines = 1)
        }
        Spacer(Modifier.weight(1f))
        if (actionLabel != null && onAction != null) {
            MbText(
                actionLabel,
                MbTheme.type.label,
                MbTheme.colors.accent,
                modifier = Modifier.clickable(onClick = onAction),
            )
        }
    }
}

@Composable
fun MbDivider(modifier: Modifier = Modifier, inset: Dp = 0.dp) {
    Box(
        modifier
            .fillMaxWidth()
            .padding(start = inset)
            .height(1.dp)
            .background(MbTheme.colors.border)
    )
}
