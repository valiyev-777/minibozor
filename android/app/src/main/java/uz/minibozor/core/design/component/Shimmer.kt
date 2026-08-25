package uz.minibozor.core.design.component

import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.layout.Box
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawWithCache
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Shape
import uz.minibozor.core.design.MbTheme

/**
 * A loading placeholder that sweeps a highlight across itself.
 *
 * Used instead of a spinner while a screen's first payload is in flight: a
 * skeleton shaped like the content that is coming reads as "nearly there",
 * where a spinner alone on an empty screen reads as "nothing here".
 *
 * The animated value is read inside the draw block rather than during
 * composition, so a frame invalidates drawing only — no recomposition and no
 * relayout, which is what makes it cheap enough to put twenty of on screen.
 *
 * Size it through [modifier], the way any other box is sized.
 */
@Composable
fun MbSkeleton(
    modifier: Modifier = Modifier,
    shape: Shape = MbTheme.shapes.field,
) {
    val base = MbTheme.colors.fill
    val highlight = MbTheme.colors.hairlineStrong
        .copy(alpha = if (MbTheme.colors.isDark) 0.5f else 0.35f)

    val sweep = rememberInfiniteTransition(label = "shimmer").animateFloat(
        initialValue = 0f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(tween(1_250, easing = LinearEasing)),
        label = "sweep",
    )

    Box(
        modifier
            .clip(shape)
            .drawWithCache {
                val band = size.width * 0.55f
                val travel = size.width + band * 2f
                onDrawBehind {
                    drawRect(base)
                    val head = sweep.value * travel - band
                    drawRect(
                        Brush.linearGradient(
                            colors = listOf(Color.Transparent, highlight, Color.Transparent),
                            start = Offset(head, 0f),
                            end = Offset(head + band, size.height),
                        )
                    )
                }
            }
    )
}
