package uz.minibozor.core.design.component

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import uz.minibozor.core.design.MbText
import uz.minibozor.core.design.MbTheme

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
            .clickable(enabled = enabled, onClick = onClick)
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

/** Square-ish size chip (39–46, S–XXL) from the product page. */
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
            .clip(MbTheme.shapes.field)
            .background(if (selected) MbTheme.colors.inverse else MbTheme.colors.surface)
            .border(
                width = if (selected) 1.6.dp else 1.dp,
                color = if (selected) MbTheme.colors.inverse else MbTheme.colors.border,
                shape = MbTheme.shapes.field,
            )
            .clickable(enabled = enabled, onClick = onClick)
            .padding(horizontal = 16.dp, vertical = 11.dp),
        contentAlignment = Alignment.Center,
    ) {
        MbText(
            label,
            MbTheme.type.label,
            when {
                !enabled -> MbTheme.colors.disabled
                selected -> MbTheme.colors.onInverse
                else -> MbTheme.colors.textSecondary
            },
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
