package uz.minibozor.core.design.component

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.layout.Box
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.Stable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.Dp
import uz.minibozor.core.design.MbMotion

/**
 * Which of a page's blocks have already been seen, and whether the page is on
 * its way out.
 *
 * Hoisted out of the blocks themselves for two reasons. A lazy list disposes an
 * item the moment it scrolls off, so a block that animated itself on first
 * composition would play its entrance again every time the customer scrolled
 * back up to it — [firstShow] is what makes an entrance happen once. And the
 * exit is a page-level fact: the back button has to be able to tell every block
 * to leave, then wait for them, before the navigation actually happens.
 */
@Stable
class MbRevealState {
    /** True once the page has been asked to leave. */
    var leaving by mutableStateOf(false)
        private set

    private val shown = mutableSetOf<String>()

    /** True the first time this block is composed, false on every later one. */
    fun firstShow(key: String): Boolean = shown.add(key)

    fun leave() {
        leaving = true
    }
}

@Composable
fun rememberMbRevealState(): MbRevealState = remember { MbRevealState() }

/**
 * One block of a page, fading up and rising into place — and, when the page
 * leaves, sinking back the way it came.
 *
 * [index] is the block's place in the running order; the entrance is staggered
 * by it so the page assembles from the top down rather than flashing in at
 * once, and the exit is staggered against it so the page comes apart from the
 * bottom up. Both are read in the layer phase, so following the animation costs
 * a transform per frame and no recomposition of the block's own content.
 */
@Composable
fun MbReveal(
    state: MbRevealState,
    key: String,
    index: Int,
    modifier: Modifier = Modifier,
    /**
     * How far the block travels as it fades.
     *
     * Zero for a block that runs to the top of the screen — a photograph under
     * the status bar cannot rise into place without showing a strip of bare page
     * above it for as long as the entrance lasts. Those fade and stay put.
     */
    rise: Dp = MbMotion.Rise,
    content: @Composable () -> Unit,
) {
    // A block scrolled back into view is already known: it takes its place at
    // full strength instead of playing the entrance a second time.
    val animate = remember(key) { state.firstShow(key) }
    var entered by remember(key) { mutableStateOf(!animate) }
    LaunchedEffect(key) { entered = true }

    val leaving = state.leaving
    val progress by animateFloatAsState(
        targetValue = if (entered && !leaving) 1f else 0f,
        animationSpec = tween(
            durationMillis = if (leaving) MbMotion.Quick else MbMotion.Emphasized,
            delayMillis = if (leaving) MbMotion.staggerOut(index) else MbMotion.stagger(index),
            easing = if (leaving) MbMotion.EaseIn else MbMotion.EaseOut,
        ),
        label = "reveal",
    )

    val risePx = with(LocalDensity.current) { rise.toPx() }
    Box(
        modifier.graphicsLayer {
            alpha = progress
            translationY = (1f - progress) * risePx
        }
    ) {
        content()
    }
}
