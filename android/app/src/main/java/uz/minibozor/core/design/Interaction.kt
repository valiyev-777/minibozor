package uz.minibozor.core.design

import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.composed
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Shape

/**
 * A tap target whose press ripple follows [shape].
 *
 * `clickable` draws its indication inside the node's own bounds, so a rounded
 * card with a bare `clickable` flashes a rectangle in its corners. Clipping
 * first is what makes the ripple take the card's shape — the ordering matters,
 * which is why this exists rather than each call site remembering it.
 */
fun Modifier.mbClickable(
    shape: Shape,
    enabled: Boolean = true,
    onClick: () -> Unit,
): Modifier = this
    .clip(shape)
    .clickable(enabled = enabled, onClick = onClick)

/**
 * A tap target with no ripple at all — for inline text links and bare icons,
 * where a flashing block is more distracting than the tap is informative.
 */
fun Modifier.mbTap(enabled: Boolean = true, onClick: () -> Unit): Modifier = composed {
    clickable(
        enabled = enabled,
        interactionSource = androidx.compose.runtime.remember { MutableInteractionSource() },
        indication = null,
        onClick = onClick,
    )
}
