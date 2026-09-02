package uz.minibozor.core.design

import androidx.compose.animation.core.Easing
import androidx.compose.animation.core.FastOutLinearInEasing
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.LinearOutSlowInEasing
import androidx.compose.animation.core.TweenSpec
import androidx.compose.animation.core.tween
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp

/**
 * How long the app's own motion takes, and on what curve.
 *
 * Three durations, not a number per call site. Everything the product page
 * animates sits between a fifth and a third of a second: under 200 ms a
 * transition reads as a jump, and over 350 ms the customer is waiting for the
 * interface to finish having an opinion. Anything that has to feel instant —
 * the press dip on a tile — takes [Quick]; anything the eye follows across the
 * screen — a photograph opening, a panel rising into place — takes
 * [Emphasized].
 *
 * The curves are the platform's standard ones rather than bespoke beziers:
 * [Ease] for something that starts and stops on screen, [EaseOut] for something
 * arriving, [EaseIn] for something leaving. Springs are still the right answer
 * where a control settles under the finger (the chevrons, the stepper); these
 * are for the choreography, where a known duration is what lets several things
 * be staggered against each other.
 */
object MbMotion {
    /** A press, a tint, a swap — fast enough to read as the touch itself. */
    const val Quick = 200

    /** The default: a panel appearing, a bar taking something over. */
    const val Standard = 280

    /** A photograph crossing the screen, or the page arriving. */
    const val Emphasized = 340

    /** The gap between one block entering and the next. */
    const val StaggerStep = 45

    /** Blocks past this many stop being delayed further. */
    const val StaggerCap = 4

    /** How far a block rises into place as it fades up. */
    val Rise: Dp = 18.dp

    /** Starts and stops on screen. */
    val Ease: Easing = FastOutSlowInEasing

    /** Arriving: quick off the mark, settles gently. */
    val EaseOut: Easing = LinearOutSlowInEasing

    /** Leaving: gives way slowly, then goes. */
    val EaseIn: Easing = FastOutLinearInEasing

    fun <T> quick(delay: Int = 0): TweenSpec<T> = tween(Quick, delay, Ease)

    fun <T> standard(delay: Int = 0): TweenSpec<T> = tween(Standard, delay, Ease)

    fun <T> emphasized(delay: Int = 0): TweenSpec<T> = tween(Emphasized, delay, Ease)

    /** The delay the [index]th block waits before entering. */
    fun stagger(index: Int): Int = StaggerStep * index.coerceIn(0, StaggerCap)

    /** The same, in reverse: the last block in leaves first. */
    fun staggerOut(index: Int): Int = (StaggerStep / 2) * (StaggerCap - index.coerceIn(0, StaggerCap))

    /** How long a page needs to clear itself before it may be navigated away. */
    const val PageExit = Quick + (StaggerStep / 2) * StaggerCap
}
