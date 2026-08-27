package uz.minibozor.core.design.component

import uz.minibozor.core.util.mediaUrl
import androidx.compose.ui.layout.ContentScale
import coil.compose.AsyncImage
import androidx.compose.animation.core.animateDpAsState
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import uz.minibozor.core.design.MbText
import uz.minibozor.core.design.MbTheme
import uz.minibozor.core.design.mbClickable
import uz.minibozor.core.design.icon.MbIcon

/**
 * The tappable list row used by the catalogue, profile menu, settings and help
 * screens: glyph in a tinted square, label, optional subtitle, trailing meta and
 * a chevron.
 */
@Composable
fun MbListRow(
    label: String,
    modifier: Modifier = Modifier,
    glyph: String? = null,
    /** A supplied picture for the leading square; falls back to [glyph]. */
    imageUrl: String? = null,
    subtitle: String? = null,
    meta: String? = null,
    showChevron: Boolean = true,
    tint: Color = MbTheme.colors.ink,
    onClick: (() -> Unit)? = null,
    /**
     * Inset for the row's own content.
     *
     * Padding the row from the outside would shrink the tap target with it —
     * the press highlight then drew as a smaller rounded block floating inside
     * the card instead of washing the whole row. Passing the inset here keeps
     * the target full-width and moves only the content in.
     */
    contentPadding: Dp = 0.dp,
    trailing: @Composable (() -> Unit)? = null,
) {
    Row(
        modifier
            .fillMaxWidth()
            .let { if (onClick != null) it.mbClickable(MbTheme.shapes.field, onClick = onClick) else it }
            .padding(horizontal = contentPadding, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        if (imageUrl != null || glyph != null) {
            Box(
                Modifier
                    .size(38.dp)
                    .clip(RoundedCornerShape(12.dp))
                    .background(MbTheme.colors.fill),
                contentAlignment = Alignment.Center,
            ) {
                if (imageUrl != null) {
                    AsyncImage(
                        model = imageUrl.mediaUrl(),
                        contentDescription = null,
                        contentScale = ContentScale.Fit,
                        modifier = Modifier.size(30.dp),
                    )
                } else {
                    MbIcon(glyph!!, size = 18.dp, tint = tint)
                }
            }
        }
        Column(Modifier.weight(1f)) {
            MbText(label, MbTheme.type.body.copy(fontWeight = androidx.compose.ui.text.font.FontWeight.Bold), tint, maxLines = 1)
            if (subtitle != null) {
                MbText(subtitle, MbTheme.type.meta, MbTheme.colors.icon, maxLines = 2)
            }
        }
        if (trailing != null) {
            trailing()
        } else {
            if (!meta.isNullOrBlank()) {
                MbText(meta, MbTheme.type.caption, MbTheme.colors.icon, maxLines = 1)
            }
            if (showChevron) {
                MbText("›", MbTheme.type.title3, MbTheme.colors.hairlineStrong)
            }
        }
    }
}

/** Switch row — notification preferences, location, night mode. */
@Composable
fun MbToggleRow(
    label: String,
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit,
    modifier: Modifier = Modifier,
    glyph: String? = null,
    /** A supplied picture for the leading square; falls back to [glyph]. */
    imageUrl: String? = null,
    subtitle: String? = null,
    contentPadding: Dp = 0.dp,
) {
    MbListRow(
        label = label,
        glyph = glyph,
        subtitle = subtitle,
        showChevron = false,
        modifier = modifier,
        contentPadding = contentPadding,
        onClick = { onCheckedChange(!checked) },
        trailing = { MbSwitch(checked = checked, onCheckedChange = onCheckedChange) },
    )
}

@Composable
fun MbSwitch(checked: Boolean, onCheckedChange: (Boolean) -> Unit) {
    val knobOffset by animateDpAsState(if (checked) 18.dp else 2.dp, label = "knob")
    Box(
        Modifier
            .size(width = 40.dp, height = 24.dp)
            .clip(CircleShape)
            .background(if (checked) MbTheme.colors.accent else MbTheme.colors.divider)
            .clickable { onCheckedChange(!checked) },
        contentAlignment = Alignment.CenterStart,
    ) {
        Box(
            Modifier
                .offset(x = knobOffset)
                .size(20.dp)
                .clip(CircleShape)
                .background(Color.White)
        )
    }
}

/** Radio row — delivery slot, payment method, cancel reason, language. */
@Composable
fun MbRadioRow(
    label: String,
    selected: Boolean,
    onSelect: () -> Unit,
    modifier: Modifier = Modifier,
    subtitle: String? = null,
    trailingLabel: String? = null,
    trailingColor: Color = MbTheme.colors.ink,
    leading: @Composable (() -> Unit)? = null,
    /**
     * Inset for the row's own content.
     *
     * Padding the row from the outside would shrink the tap target with it —
     * the press highlight then drew as a smaller rounded block floating inside
     * the card instead of washing the whole row. Passing the inset here keeps
     * the target full-width and moves only the content in.
     */
    contentPadding: Dp = 0.dp,
) {
    Row(
        modifier
            .fillMaxWidth()
            .mbClickable(MbTheme.shapes.field, onClick = onSelect)
            .padding(horizontal = contentPadding, vertical = 13.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        leading?.invoke()
        Column(Modifier.weight(1f)) {
            MbText(label, MbTheme.type.body.copy(fontWeight = androidx.compose.ui.text.font.FontWeight.Bold))
            if (subtitle != null) {
                MbText(subtitle, MbTheme.type.meta, MbTheme.colors.icon, maxLines = 2)
            }
        }
        if (trailingLabel != null) {
            MbText(trailingLabel, MbTheme.type.label, trailingColor)
        }
        MbRadio(selected)
    }
}

@Composable
fun MbRadio(selected: Boolean) {
    Box(
        Modifier
            .size(20.dp)
            .clip(CircleShape)
            .border(
                width = if (selected) 5.dp else 1.5.dp,
                color = if (selected) MbTheme.colors.accent else MbTheme.colors.hairline,
                shape = CircleShape,
            )
    )
}

/** Checkbox row — filter flags and brand lists. */
@Composable
fun MbCheckRow(
    label: String,
    checked: Boolean,
    onToggle: () -> Unit,
    modifier: Modifier = Modifier,
    subtitle: String? = null,
    count: String? = null,
    /**
     * Inset for the row's own content.
     *
     * Padding the row from the outside would shrink the tap target with it —
     * the press highlight then drew as a smaller rounded block floating inside
     * the card instead of washing the whole row. Passing the inset here keeps
     * the target full-width and moves only the content in.
     */
    contentPadding: Dp = 0.dp,
) {
    Row(
        modifier
            .fillMaxWidth()
            .mbClickable(MbTheme.shapes.field, onClick = onToggle)
            .padding(horizontal = contentPadding, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        MbCheckbox(checked)
        Column(Modifier.weight(1f)) {
            MbText(label, MbTheme.type.body.copy(fontWeight = androidx.compose.ui.text.font.FontWeight.Bold))
            if (subtitle != null) {
                MbText(subtitle, MbTheme.type.meta, MbTheme.colors.icon, maxLines = 1)
            }
        }
        if (count != null) MbText(count, MbTheme.type.caption, MbTheme.colors.icon)
    }
}

@Composable
fun MbCheckbox(checked: Boolean) {
    Box(
        Modifier
            .size(22.dp)
            .clip(RoundedCornerShape(7.dp))
            .background(if (checked) MbTheme.colors.accent else Color.Transparent)
            .border(
                width = if (checked) 0.dp else 1.5.dp,
                color = if (checked) Color.Transparent else MbTheme.colors.hairline,
                shape = RoundedCornerShape(7.dp),
            ),
        contentAlignment = Alignment.Center,
    ) {
        if (checked) MbText("✓", MbTheme.type.micro, Color.White)
    }
}

/** A "key — value" line, used by the order summary and product specs. */
@Composable
fun MbKeyValueRow(key: String, value: String, modifier: Modifier = Modifier) {
    Row(
        modifier
            .fillMaxWidth()
            .padding(vertical = 9.dp),
        verticalAlignment = Alignment.Top,
    ) {
        MbText(key, MbTheme.type.bodySmall, MbTheme.colors.icon, modifier = Modifier.weight(1f))
        Spacer(Modifier.width(16.dp))
        MbText(
            value,
            MbTheme.type.bodySmall.copy(fontWeight = androidx.compose.ui.text.font.FontWeight.Bold),
            MbTheme.colors.ink,
            modifier = Modifier.weight(1.4f),
            textAlign = androidx.compose.ui.text.style.TextAlign.End,
        )
    }
}

/** Totals line in the cart and checkout; [strong] renders the grand total. */
@Composable
fun MbTotalRow(
    label: String,
    value: String,
    strong: Boolean = false,
    valueColor: Color = MbTheme.colors.ink,
    modifier: Modifier = Modifier,
) {
    Row(
        modifier
            .fillMaxWidth()
            .padding(vertical = if (strong) 8.dp else 6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        MbText(
            label,
            if (strong) MbTheme.type.sectionHead else MbTheme.type.bodySmall,
            if (strong) MbTheme.colors.ink else MbTheme.colors.textSecondary,
        )
        Spacer(Modifier.weight(1f))
        MbText(value, if (strong) MbTheme.type.price else MbTheme.type.label, valueColor)
    }
}

@Composable
fun MbSpacerLine(height: Int = 12) = Spacer(Modifier.height(height.dp))
