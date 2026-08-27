package uz.minibozor.core.design

import android.os.Build
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.composed
import androidx.compose.ui.draw.drawWithContent
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.BlurEffect
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.TileMode
import androidx.compose.ui.graphics.drawscope.translate
import androidx.compose.ui.graphics.layer.GraphicsLayer
import androidx.compose.ui.graphics.layer.drawLayer
import androidx.compose.ui.graphics.rememberGraphicsLayer
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.layout.positionInRoot
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp

/**
 * Whether the floating bar blurs the live screen behind it.
 *
 * Off, and deliberately. A live backdrop costs, on every single frame: the whole
 * screen recorded into an offscreen layer, that layer composited back over the
 * real one, and a 22 dp Gaussian pass over the strip behind the bar. That tax
 * lands on exactly the frames a scrolling product feed cannot spare, and the
 * bar's own fill is 94% opaque — almost none of the blur was visible through it.
 *
 * The fallback below it is the translucent slab the bar shipped with. Flip this
 * to true to compare; nothing else needs changing.
 */
val MbLiveGlass: Boolean = false

/**
 * The pieces of a live "liquid glass" panel: [glassSource] records what a
 * screen draws, and [liquidGlass] replays that recording behind a panel,
 * blurred and tinted — so the bar genuinely refracts the content scrolling
 * under it instead of faking it with a flat translucent fill.
 *
 * Real blur needs RenderEffect (API 31+); older devices fall back to the
 * opaque-ish tint alone, which is what the bar shipped with before.
 */
class GlassBackdrop internal constructor(internal val content: GraphicsLayer) {
    internal var contentOrigin by mutableStateOf(Offset.Zero)
}

@Composable
fun rememberGlassBackdrop(): GlassBackdrop {
    val layer = rememberGraphicsLayer()
    return remember(layer) { GlassBackdrop(layer) }
}

/** Records everything this node draws so glass panels can show it blurred. */
fun Modifier.glassSource(backdrop: GlassBackdrop): Modifier = this
    .onGloballyPositioned { backdrop.contentOrigin = it.positionInRoot() }
    .drawWithContent {
        backdrop.content.record { this@drawWithContent.drawContent() }
        drawLayer(backdrop.content)
    }

/**
 * Draws the recorded content blurred behind this node, then washes it with
 * [tint]. Clip to the panel's shape before this modifier — the drawing itself
 * is unbounded. On devices without RenderEffect, draws [fallback] instead.
 */
fun Modifier.liquidGlass(
    backdrop: GlassBackdrop,
    tint: Color,
    fallback: Color,
    blurRadius: Dp = 22.dp,
): Modifier = composed {
    val blurLayer = rememberGraphicsLayer()
    var origin by remember { mutableStateOf(Offset.Zero) }

    onGloballyPositioned { origin = it.positionInRoot() }
        .drawWithContent {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                val shift = backdrop.contentOrigin - origin
                blurLayer.record {
                    translate(shift.x, shift.y) { drawLayer(backdrop.content) }
                }
                blurLayer.renderEffect =
                    BlurEffect(blurRadius.toPx(), blurRadius.toPx(), TileMode.Clamp)
                drawLayer(blurLayer)
                drawRect(tint)
                // A faint top-lit sheen, which is most of what reads as "glass".
                drawRect(
                    Brush.verticalGradient(
                        0f to Color.White.copy(alpha = 0.20f),
                        0.45f to Color.Transparent,
                    )
                )
            } else {
                drawRect(fallback)
            }
            drawContent()
        }
}
