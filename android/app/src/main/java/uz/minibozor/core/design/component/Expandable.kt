package uz.minibozor.core.design.component

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.animateContentSize
import androidx.compose.animation.core.FastOutLinearInEasing
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.LinearOutSlowInEasing
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.animation.expandVertically
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.shrinkVertically
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.unit.dp
import uz.minibozor.R
import uz.minibozor.core.design.MbText
import uz.minibozor.core.design.MbTheme
import uz.minibozor.core.design.mbTap
import uz.minibozor.core.design.icon.MbIcon

/**
 * A section that folds away, for the parts of a product page most people
 * scroll straight past.
 *
 * The chevron turns rather than swapping glyph, and the body expands rather
 * than appearing, so the row above never jumps.
 */
@Composable
fun MbExpandableSection(
    title: String,
    modifier: Modifier = Modifier,
    subtitle: String? = null,
    initiallyExpanded: Boolean = false,
    content: @Composable () -> Unit,
) {
    var expanded by remember { mutableStateOf(initiallyExpanded) }
    // A spring, so the chevron settles rather than stopping dead on the frame
    // the height animation is still finishing.
    val turn by animateFloatAsState(
        targetValue = if (expanded) 180f else 0f,
        animationSpec = spring(dampingRatio = 0.7f, stiffness = 380f),
        label = "chevron",
    )

    Column(modifier.fillMaxWidth()) {
        Row(
            Modifier
                .fillMaxWidth()
                .mbTap { expanded = !expanded }
                .padding(vertical = 2.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(Modifier.weight(1f)) {
                MbText(title, MbTheme.type.title3)
                if (subtitle != null) {
                    MbText(subtitle, MbTheme.type.meta, MbTheme.colors.textQuaternary)
                }
            }
            MbIcon(
                "chevron-down",
                size = 18.dp,
                tint = MbTheme.colors.icon,
                modifier = Modifier.graphicsLayer { rotationZ = turn },
            )
        }
        AnimatedVisibility(
            visible = expanded,
            // The height leads and the text follows it in, rather than both
            // starting together — fading up from nothing while the box is
            // still a sliver is what makes an accordion look cheap. Closing
            // is the reverse and quicker, since nobody watches a fold shut.
            enter = expandVertically(
                animationSpec = spring(dampingRatio = 0.9f, stiffness = 320f),
            ) + fadeIn(tween(200, delayMillis = 90, easing = LinearOutSlowInEasing)),
            exit = shrinkVertically(
                animationSpec = spring(dampingRatio = 1f, stiffness = 420f),
            ) + fadeOut(tween(110, easing = FastOutLinearInEasing)),
        ) {
            Column {
                Spacer(Modifier.height(10.dp))
                content()
            }
        }
    }
}

/**
 * Text clamped to [collapsedLines] with a toggle under it.
 *
 * The toggle only appears when the text really is longer than that — measured,
 * not guessed from its length, since how many lines a paragraph takes depends
 * on the screen it is on.
 */
@Composable
fun MbCollapsibleText(
    text: String,
    modifier: Modifier = Modifier,
    collapsedLines: Int = 4,
    style: TextStyle = MbTheme.type.bodySmall,
) {
    var expanded by remember(text) { mutableStateOf(false) }
    var overflows by remember(text) { mutableStateOf(false) }
    val turn by animateFloatAsState(
        targetValue = if (expanded) 180f else 0f,
        animationSpec = spring(dampingRatio = 0.7f, stiffness = 380f),
        label = "moreChevron",
    )

    Column(modifier.fillMaxWidth()) {
        MbText(
            text,
            style,
            MbTheme.colors.inkSoft,
            maxLines = if (expanded) Int.MAX_VALUE else collapsedLines,
            // The paragraph grows into its new height instead of jumping to it.
            modifier = Modifier.animateContentSize(
                animationSpec = spring(dampingRatio = 0.9f, stiffness = 320f),
            ),
            onTextLayout = { result: TextLayoutResult ->
                if (!expanded && result.hasVisualOverflow) overflows = true
            },
        )
        if (overflows) {
            Spacer(Modifier.height(8.dp))
            Row(
                Modifier.mbTap { expanded = !expanded },
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                MbText(
                    stringResource(if (expanded) R.string.yopish else R.string.batafsil),
                    MbTheme.type.label,
                    MbTheme.colors.accent,
                )
                MbIcon(
                    "chevron-down",
                    size = 14.dp,
                    tint = MbTheme.colors.accent,
                    modifier = Modifier.graphicsLayer { rotationZ = turn },
                )
            }
        }
    }
}
