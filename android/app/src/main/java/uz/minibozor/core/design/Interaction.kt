package uz.minibozor.core.design

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.IndicationNodeFactory
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.InteractionSource
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.PressInteraction
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.composed
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.graphics.drawOutline
import androidx.compose.ui.graphics.drawscope.ContentDrawScope
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.node.DelegatableNode
import androidx.compose.ui.node.DrawModifierNode
import kotlinx.coroutines.launch

/**
 * How strongly a tap washes whatever it lands on.
 *
 * One value so the Material ripple under [mbClickable] and the highlight
 * [mbPressable] draws agree — two numbers drifted apart once already. Kept
 * low: the ripple takes its hue from the content colour, which on a light
 * theme is near-black, and anything stronger flashed a dark disc across a
 * white card.
 */
const val MbPressAlpha = 0.05f

/**
 * A tap target whose press ripple follows [shape].
 *
 * `clickable` draws its indication inside the node's own bounds, so a rounded
 * card with a bare `clickable` flashes a rectangle in its corners. Clipping
 * first is what makes the ripple take the card's shape — the ordering matters,
 * which is why this exists rather than each call site remembering it.
 *
 * The clip applies to the CONTENT too, so this is only for targets that draw
 * a background inside the shape (chips, buttons, rows). A tile whose text runs
 * to its bottom edge would get the last line shaved by the corner arcs — use
 * [mbPressable] there instead.
 */
fun Modifier.mbClickable(
    shape: Shape,
    enabled: Boolean = true,
    onClick: () -> Unit,
): Modifier = this
    .clip(shape)
    .clickable(enabled = enabled, onClick = onClick)

/**
 * Press feedback for content tiles: a soft highlight in [shape] drawn over the
 * content instead of clipping to it. [mbClickable]'s clip cuts whatever touches
 * the corners — on product tiles the second title line lost its first and last
 * glyphs to the corner arcs — while this keeps every pixel of content and still
 * presses in the tile's rounded shape.
 */
fun Modifier.mbPressable(
    shape: Shape,
    color: Color,
    enabled: Boolean = true,
    onClick: () -> Unit,
): Modifier = this.clickable(
    interactionSource = null,
    indication = MbPressHighlight(shape, color),
    enabled = enabled,
    onClick = onClick,
)

/**
 * The highlight [mbPressable] draws, handed out on its own.
 *
 * For call sites that need to own the interaction source rather than let
 * `clickable` create one — a card whose whole body dips under the finger has to
 * read the same presses the highlight is drawn from, so the dip and the wash
 * begin on the same frame. See [mbPressDip].
 */
fun mbPressIndication(shape: Shape, color: Color): IndicationNodeFactory =
    MbPressHighlight(shape, color)

/** The press source a card's dip and its highlight share. */
@Composable
fun rememberMbPress(): MutableInteractionSource = remember { MutableInteractionSource() }

/**
 * Dips everything drawn to the right of it while [interaction] is pressed.
 *
 * A card is a large target, and a wash of ink over a large target is a weak
 * signal — the tile is 180 dp across and the highlight is five percent of ink.
 * Taking the whole card down a fraction is the part the eye actually catches,
 * and it is the same gesture the app's buttons already make.
 *
 * Placed at the head of a card's modifier chain, before the shadow and the
 * background, so the surface and its shadow scale with the content rather than
 * standing still around a shrinking picture.
 */
@Composable
fun Modifier.mbPressDip(
    interaction: MutableInteractionSource,
    pressedScale: Float = 0.975f,
): Modifier {
    val pressed by interaction.collectIsPressedAsState()
    // Down fast, back slower: the dip should land with the finger and recover
    // gently enough to be seen recovering.
    val scale by animateFloatAsState(
        targetValue = if (pressed) pressedScale else 1f,
        animationSpec = tween(
            durationMillis = if (pressed) MbMotion.Quick else MbMotion.Standard,
            easing = MbMotion.Ease,
        ),
        label = "pressDip",
    )
    return graphicsLayer {
        scaleX = scale
        scaleY = scale
    }
}

private data class MbPressHighlight(
    val shape: Shape,
    val color: Color,
) : IndicationNodeFactory {
    override fun create(interactionSource: InteractionSource): DelegatableNode =
        PressHighlightNode(interactionSource, shape, color)
}

private class PressHighlightNode(
    private val interactionSource: InteractionSource,
    private val shape: Shape,
    private val color: Color,
) : Modifier.Node(), DrawModifierNode {

    /** 0 = idle, 1 = pressed. Snaps in so taps feel instant, eases out. */
    private val alpha = Animatable(0f)

    override fun onAttach() {
        coroutineScope.launch {
            interactionSource.interactions.collect { interaction ->
                when (interaction) {
                    is PressInteraction.Press -> launch { alpha.snapTo(1f) }
                    is PressInteraction.Release,
                    is PressInteraction.Cancel,
                    -> launch { alpha.animateTo(0f, tween(220)) }
                }
            }
        }
    }

    override fun ContentDrawScope.draw() {
        drawContent()
        val a = alpha.value
        if (a > 0f) {
            drawOutline(
                outline = shape.createOutline(size, layoutDirection, this),
                color = color,
                alpha = a,
            )
        }
    }
}

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
