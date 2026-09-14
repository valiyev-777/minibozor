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
import androidx.compose.foundation.layout.systemBars
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Scaffold
import androidx.compose.runtime.Composable
import androidx.compose.ui.draw.drawWithContent
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Shape
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
    /**
     * What is painted behind the status bar.
     *
     * The page's own ground by default, and that was every screen — which left
     * a strip of grey canvas above the white band the tabs open with, so the
     * clock sat on a step of colour that belonged to nothing. `design/screens`
     * draws it the other way round: the header's white starts at the top of the
     * phone and the clock is inside it. A screen whose first thing is a band of
     * surface passes that colour here and the step is gone.
     *
     * Painted over the frame rather than under it, because the Scaffold's own
     * container colour would cover anything drawn behind. Nothing composes into
     * that strip — the content is inset past it — so there is nothing there to
     * cover.
     */
    statusBand: Color = background,
    topBar: @Composable () -> Unit = {},
    bottomBar: @Composable () -> Unit = {},
    content: @Composable (androidx.compose.foundation.layout.PaddingValues) -> Unit,
) {
    val bandHeight = WindowInsets.statusBars.asPaddingValues().calculateTopPadding()
    Scaffold(
        modifier = modifier
            .fillMaxSize()
            .then(
                if (statusBand == background) {
                    Modifier
                } else {
                    Modifier.drawWithContent {
                        drawContent()
                        drawRect(statusBand, size = Size(size.width, bandHeight.toPx()))
                    }
                }
            ),
        containerColor = background,
        topBar = topBar,
        bottomBar = bottomBar,
        // System bars, not the status bar alone. The window is drawn edge to
        // edge, so a screen with no bottom bar of its own ran its content to
        // the physical bottom of the phone: the last thing on an order — the
        // button that cancels it — sat on the gesture handle with 12 dp between
        // them. A screen that does have a bottom bar is unaffected, since the
        // Scaffold measures the bar itself for that edge.
        contentWindowInsets = WindowInsets.systemBars,
        content = content,
    )
}

/**
 * The header a tab's own screen wears: its name, and room for one note beside
 * it.
 *
 * One component rather than each screen rolling its own row, because they had
 * drifted — the cart's name sat two points lower than the catalogue's, and the
 * profile had no header at all, so its first card began right under the clock.
 * The status bar is already cleared by [MbScreen], so the padding here is the
 * breathing room above the name and nothing else, which makes it the same
 * distance from the clock on every phone.
 */
@Composable
fun MbTabHeader(
    title: String,
    modifier: Modifier = Modifier,
    trailing: @Composable (() -> Unit)? = null,
    below: @Composable (() -> Unit)? = null,
) {
    Column(
        modifier
            .fillMaxWidth()
            .background(MbTheme.colors.surface)
            .padding(start = 20.dp, end = 20.dp, top = 18.dp, bottom = 14.dp)
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            MbText(title, MbTheme.type.title1)
            Spacer(Modifier.weight(1f))
            trailing?.invoke()
        }
        if (below != null) {
            Spacer(Modifier.height(12.dp))
            below()
        }
    }
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
    /**
     * Fades the title in and out without relaying the row out. The product
     * screen uses it to bring the product name up into the bar only once the
     * gallery has scrolled away, and reads the value in the layer phase so the
     * fade costs no recomposition.
     */
    titleAlpha: () -> Float = { 1f },
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
                MbText(
                    title,
                    MbTheme.type.title3,
                    maxLines = 1,
                    modifier = Modifier.graphicsLayer { alpha = titleAlpha() },
                )
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
            // Clipped first, so the press wash is a disc rather than a square
            // in the button's corners.
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
    /**
     * Square it off for a section that runs edge to edge — rounded corners
     * against the screen edge look like a card that did not fit.
     */
    shape: Shape = MbTheme.shapes.card,
    onClick: (() -> Unit)? = null,
    content: @Composable ColumnScope.() -> Unit,
) {
    Column(
        modifier
            .fillMaxWidth()
            .clip(shape)
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
                // A pill-shaped target with room around the word, rather than a
                // bare clickable that flashes a rectangle the exact size of the
                // glyphs. The padding is the tap area; the clip is what keeps
                // the press round.
                modifier = Modifier
                    .clip(MbTheme.shapes.chip)
                    .clickable(onClick = onAction)
                    .padding(horizontal = 8.dp, vertical = 5.dp),
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
