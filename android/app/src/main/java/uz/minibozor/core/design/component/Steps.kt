package uz.minibozor.core.design.component

import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp
import uz.minibozor.core.design.MbMotion
import uz.minibozor.core.design.MbText
import uz.minibozor.core.design.MbTheme

/**
 * Where the customer is in a run of screens, as a row of rails.
 *
 * Four short bars rather than numbered circles: at this width a circle with a
 * digit in it is either too small to read or too large to sit under a title,
 * and what someone wants here is not "step 2 of 4" but "how much of this is
 * behind me". A filled rail reads as ground covered without being counted.
 *
 * The rail for the step in hand is filled like the ones behind it — being on a
 * step is progress, not a promise — and its label is the only one set in ink,
 * so the eye lands on where you are rather than on where you have been.
 */
@Composable
fun MbStepBar(
    steps: List<String>,
    current: Int,
    modifier: Modifier = Modifier,
) {
    Row(
        modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        steps.forEachIndexed { index, label ->
            val done = index <= current
            // Animated, because the bar is the one thing on the screen that
            // answers a step being finished somewhere else — coming back from
            // the address form with the rail already filled says nothing
            // happened, and filling it as the screen settles says it did.
            val rail by animateColorAsState(
                if (done) MbTheme.colors.accent else MbTheme.colors.divider,
                tween(MbMotion.Emphasized, easing = MbMotion.EaseOut),
                label = "rail",
            )
            Column(
                Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(5.dp),
            ) {
                Spacer(
                    Modifier
                        .fillMaxWidth()
                        .height(3.dp)
                        .clip(MbTheme.shapes.chip)
                        .background(rail)
                )
                MbText(
                    label,
                    MbTheme.type.micro,
                    when {
                        index == current -> MbTheme.colors.ink
                        done -> MbTheme.colors.textTertiary
                        else -> MbTheme.colors.disabled
                    },
                    maxLines = 1,
                )
            }
        }
    }
}
