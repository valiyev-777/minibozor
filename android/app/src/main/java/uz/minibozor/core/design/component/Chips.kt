package uz.minibozor.core.design.component

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.unit.dp
import uz.minibozor.core.design.MbText
import uz.minibozor.core.design.MbTheme
import uz.minibozor.core.design.mbPressable

/**
 * Selectable pill. The design inverts to solid ink when selected and keeps a
 * hairline outline when not — the same treatment for sizes, tags and sorts.
 */
@Composable
fun MbChip(
    label: String,
    selected: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
) {
    Box(
        modifier
            .clip(MbTheme.shapes.chip)
            .background(
                when {
                    !enabled -> MbTheme.colors.fill
                    selected -> MbTheme.colors.inverse
                    else -> MbTheme.colors.surface
                }
            )
            .border(
                width = if (selected || !enabled) 0.dp else 1.dp,
                color = if (selected || !enabled) Color.Transparent else MbTheme.colors.border,
                shape = MbTheme.shapes.chip,
            )
            // The app's own highlight rather than whatever `LocalIndication`
            // happens to be here. The theme hands out a 5% ripple, but a
            // modal sheet is its own window and anything composed outside that
            // provider falls back to Foundation's debugging indication —
            // flat black at nearly a third opacity, which is the dark
            // rectangle that turned up under the filter's controls.
            .mbPressable(
                MbTheme.shapes.chip,
                if (selected) MbTheme.colors.onInverse else MbTheme.colors.ink,
                enabled = enabled,
                onClick = onClick,
            )
            .padding(horizontal = 14.dp, vertical = 9.dp),
        contentAlignment = Alignment.Center,
    ) {
        MbText(
            label,
            MbTheme.type.caption,
            when {
                !enabled -> MbTheme.colors.disabled
                selected -> MbTheme.colors.onInverse
                else -> MbTheme.colors.inkSoft
            },
            maxLines = 1,
        )
    }
}

/**
 * Square-ish size chip (39–46, S–XXL) from the product page.
 *
 * The selected one is ringed rather than filled: a size is picked from a row of
 * eight, and a solid black block among seven outlines reads as a different kind
 * of control rather than as "this one". The ring is drawn at 2 dp so it is
 * unmistakable at a glance.
 *
 * Sized so a shoe's whole size run — 39 through 46 — reads as one row rather
 * than two. It was 58 dp wide, which put the last sizes on a line of their own,
 * and a size run broken across two rows reads as two different things being
 * asked. Eight of these plus their 5 dp gaps come to 339 dp, inside the 343 dp a
 * card leaves on the narrowest phone the design is drawn for; a longer label
 * ("41 mm", "XXL") grows its own chip and the row scrolls instead of wrapping.
 */
@Composable
fun MbSizeChip(
    label: String,
    selected: Boolean,
    onClick: () -> Unit,
    enabled: Boolean = true,
    modifier: Modifier = Modifier,
) {
    Box(
        modifier
            .defaultMinSize(minWidth = 38.dp, minHeight = 40.dp)
            .clip(MbTheme.shapes.field)
            .background(if (enabled) MbTheme.colors.surface else MbTheme.colors.fill)
            .border(
                width = if (selected) 2.dp else 1.dp,
                color = when {
                    selected -> MbTheme.colors.ink
                    !enabled -> MbTheme.colors.border
                    else -> MbTheme.colors.hairline
                },
                shape = MbTheme.shapes.field,
            )
            // See MbChip: the highlight is named rather than inherited, so a
            // sheet in its own window cannot fall back to the debugging one.
            .mbPressable(
                MbTheme.shapes.field,
                MbTheme.colors.ink,
                enabled = enabled,
                onClick = onClick,
            )
            // Horizontal padding only has to hold a longer label — "41 mm",
            // "XXL" — off the border; the width above is what sets the size of
            // an ordinary two-digit chip.
            .padding(horizontal = 7.dp, vertical = 7.dp),
        contentAlignment = Alignment.Center,
    ) {
        MbText(
            label,
            MbTheme.type.label.copy(
                fontWeight = if (selected) FontWeight.ExtraBold else FontWeight.Bold,
                textDecoration = if (enabled) null else TextDecoration.LineThrough,
            ),
            when {
                !enabled -> MbTheme.colors.disabled
                selected -> MbTheme.colors.ink
                else -> MbTheme.colors.inkMuted
            },
            maxLines = 1,
        )
    }
}

/** Status pill: order state, review moderation state, address label. */
@Composable
fun MbStatusPill(
    label: String,
    background: Color,
    contentColor: Color,
    modifier: Modifier = Modifier,
) {
    Box(
        modifier
            .clip(MbTheme.shapes.badge)
            .background(background)
            .padding(horizontal = 8.dp, vertical = 4.dp),
    ) {
        MbText(label, MbTheme.type.badge, contentColor, maxLines = 1)
    }
}
