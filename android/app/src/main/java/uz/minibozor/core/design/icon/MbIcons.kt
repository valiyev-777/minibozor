package uz.minibozor.core.design.icon

import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.graphics.vector.addPathNodes
import androidx.compose.ui.graphics.vector.rememberVectorPainter
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.size
import androidx.compose.ui.graphics.ColorFilter
import uz.minibozor.core.design.MbTheme

/**
 * The icon set from the design, as SVG path data on a 24x24 grid.
 *
 * The design draws every glyph as a 1.6-weight round-capped stroke, so these are
 * built as stroked vectors rather than filled ones — that keeps a 20 dp icon and
 * a 44 dp icon visually identical to the source.
 *
 * Generated from `design/icons.json`; edit that file and regenerate rather than
 * hand-editing path data here.
 */
private val GLYPHS: Map<String, List<String>> = mapOf(
    "food" to listOf(
        "M4.6 12.8h14.8a7.4 7.4 0 0 1-14.8 0z",
        "M6.4 9.6c0-1.9 2.5-3.4 5.6-3.4s5.6 1.5 5.6 3.4",
        "M5 20.4h14",
    ),
    "globe" to listOf(
        "M12 3.5a8.5 8.5 0 1 0 0 17 8.5 8.5 0 0 0 0-17z",
        "M3.6 12h16.8",
        "M12 3.5c2.3 2.3 3.5 5.1 3.5 8.5S14.3 18.2 12 20.5C9.7 18.2 8.5 15.4 8.5 12S9.7 5.8 12 3.5z",
    ),
    "plant" to listOf(
        "M12 21v-7.2",
        "M12 13.8c-3.4 0-5.2-2-5.2-5.2 3.4 0 5.2 2 5.2 5.2z",
        "M12 13.8c3.4 0 5.2-2 5.2-5.2-3.4 0-5.2 2-5.2 5.2z",
    ),
    "bottle" to listOf(
        "M9 8.4h6v10.8a1.8 1.8 0 0 1-1.8 1.8h-2.4A1.8 1.8 0 0 1 9 19.2z",
        "M10.6 8.4V5.6h2.8v2.8",
        "M9.4 12.6h5.2",
    ),
    "shirt" to listOf(
        "M8.2 4 4.6 6.4 6 9.8l2.2-1v11.4h7.6V8.8l2.2 1 1.4-3.4L15.8 4",
        "M8.2 4c0 2 1.7 2.9 3.8 2.9S15.8 6 15.8 4",
    ),
    "car" to listOf(
        "M3.6 15.4h16.8v-2.9l-1.7-4.2A2 2 0 0 0 16.8 7H7.2a2 2 0 0 0-1.9 1.3l-1.7 4.2z",
        "M7 18.4v-3M17 18.4v-3",
    ),
    "phone" to listOf(
        "M7.6 3.6h8.8a1.5 1.5 0 0 1 1.5 1.5v13.8a1.5 1.5 0 0 1-1.5 1.5H7.6a1.5 1.5 0 0 1-1.5-1.5V5.1a1.5 1.5 0 0 1 1.5-1.5z",
        "M10.6 17.4h2.8",
    ),
    "washer" to listOf(
        "M5.6 3.6h12.8a1 1 0 0 1 1 1v14.8a1 1 0 0 1-1 1H5.6a1 1 0 0 1-1-1V4.6a1 1 0 0 1 1-1z",
        "M12 9.4a4.1 4.1 0 1 0 0 8.2 4.1 4.1 0 0 0 0-8.2z",
        "M8 6.6h1.6",
    ),
    "gift" to listOf(
        "M4.4 9.6h15.2v9.8a1 1 0 0 1-1 1H5.4a1 1 0 0 1-1-1z",
        "M3.6 6.2h16.8v3.4H3.6z",
        "M12 6.2v14.2",
    ),
    "backpack" to listOf(
        "M6.2 9.8A4 4 0 0 1 10.2 5.8h3.6a4 4 0 0 1 4 4v8.8a1.5 1.5 0 0 1-1.5 1.5H7.7a1.5 1.5 0 0 1-1.5-1.5z",
        "M9.6 9.4V6.6a2.4 2.4 0 0 1 4.8 0v2.8",
        "M9.4 14.6h5.2",
    ),
    "lipstick" to listOf(
        "M9.6 10.2h4.8v10.4H9.6z",
        "M10.6 10.2V6.4a1.6 1.6 0 0 1 3.2 0v3.8",
    ),
    "basket" to listOf(
        "M4.2 9.6h15.6l-1.6 9.1a1.6 1.6 0 0 1-1.6 1.3H7.4a1.6 1.6 0 0 1-1.6-1.3z",
        "M8.6 9.6 10 4.6M15.4 9.6 14 4.6",
    ),
    "ball" to listOf(
        "M12 3.5a8.5 8.5 0 1 0 0 17 8.5 8.5 0 0 0 0-17z",
        "M12 3.5v17",
        "M3.5 12h17",
    ),
    "card" to listOf(
        "M3.6 6.4h16.8v11.2H3.6z",
        "M3.6 10.4h16.8",
    ),
    "pin" to listOf(
        "M12 20.8s6.8-5.4 6.8-10.8a6.8 6.8 0 1 0-13.6 0c0 5.4 6.8 10.8 6.8 10.8z",
        "M12 12.4a2.4 2.4 0 1 0 0-4.8 2.4 2.4 0 0 0 0 4.8z",
    ),
    "bell" to listOf(
        "M6.4 17.4h11.2l-1.4-2.1v-4.1a4.2 4.2 0 0 0-8.4 0v4.1z",
        "M10.4 20h3.2",
    ),
    "star" to listOf(
        "M12 4.2l2.4 4.9 5.4.8-3.9 3.8.9 5.4-4.8-2.5-4.8 2.5.9-5.4-3.9-3.8 5.4-.8z",
    ),
    "gear" to listOf(
        "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
        "M12 3.6v2.2M12 18.2v2.2M5.2 7.8l1.9 1.1M16.9 15.1l1.9 1.1M5.2 16.2l1.9-1.1M16.9 8.9l1.9-1.1",
    ),
    "box" to listOf(
        "M4.2 8.4 12 4.4l7.8 4v7.2L12 19.6l-7.8-4z",
        "M4.2 8.4 12 12.4l7.8-4",
        "M12 12.4v7.2",
    ),
    "heart" to listOf(
        "M12 20s-7-4.4-7-9.4A4.1 4.1 0 0 1 12 7.8a4.1 4.1 0 0 1 7 2.8c0 5-7 9.4-7 9.4z",
    ),
    "ticket" to listOf(
        "M4.2 8.4h15.6v3.2a2 2 0 0 0 0 4v3.2H4.2v-3.2a2 2 0 0 0 0-4z",
        "M12 8.4v11.2",
    ),
    "ret" to listOf(
        "M9.2 6.4 5.6 10l3.6 3.6",
        "M5.6 10h8.8a4.6 4.6 0 0 1 0 9.2h-2.8",
    ),
    "headset" to listOf(
        "M5.2 15v-3a6.8 6.8 0 0 1 13.6 0v3",
        "M5.2 14.4h2.6v5.2H6.2a1 1 0 0 1-1-1z",
        "M18.8 14.4h-2.6v5.2h1.6a1 1 0 0 0 1-1z",
    ),
    "clock" to listOf(
        "M12 3.6a8.4 8.4 0 1 0 0 16.8 8.4 8.4 0 0 0 0-16.8z",
        "M12 7.8v4.4l3 1.8",
    ),
    "search" to listOf(
        "M11 4.6a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13z",
        "m16 16 4 4",
    ),
    "sofa" to listOf(
        "M4.6 12.6a1.8 1.8 0 0 1 3.6 0v2.4h7.6v-2.4a1.8 1.8 0 0 1 3.6 0v5.4H4.6z",
        "M6.6 12.4V8.6a2 2 0 0 1 2-2h6.8a2 2 0 0 1 2 2v3.8",
    ),
    "home" to listOf(
        "M3 10.2 12 3.4l9 6.8V20a1 1 0 0 1-1 1h-5v-6H10v6H4a1 1 0 0 1-1-1z",
    ),
    "cart" to listOf(
        "M5.5 8h13l-1.1 11.1a1.6 1.6 0 0 1-1.6 1.4H8.2a1.6 1.6 0 0 1-1.6-1.4z",
        "M9 8V6.4A3 3 0 0 1 12 3.4a3 3 0 0 1 3 3V8",
    ),
    "user" to listOf(
        "M12 4.8a3.6 3.6 0 1 0 0 7.2 3.6 3.6 0 0 0 0-7.2z",
        "M4.6 20.4c1-3.6 3.9-5.4 7.4-5.4s6.4 1.8 7.4 5.4",
    ),
    "grid" to listOf(
        "M3.4 5.6a2.2 2.2 0 0 1 2.2-2.2h2.8a2.2 2.2 0 0 1 2.2 2.2v2.8a2.2 2.2 0 0 1-2.2 2.2H5.6a2.2 2.2 0 0 1-2.2-2.2z",
        "M13.4 5.6a2.2 2.2 0 0 1 2.2-2.2h2.8a2.2 2.2 0 0 1 2.2 2.2v2.8a2.2 2.2 0 0 1-2.2 2.2h-2.8a2.2 2.2 0 0 1-2.2-2.2zM3.4 15.6a2.2 2.2 0 0 1 2.2-2.2h2.8a2.2 2.2 0 0 1 2.2 2.2v2.8a2.2 2.2 0 0 1-2.2 2.2H5.6a2.2 2.2 0 0 1-2.2-2.2z",
        "M13.4 15.6a2.2 2.2 0 0 1 2.2-2.2h2.8a2.2 2.2 0 0 1 2.2 2.2v2.8a2.2 2.2 0 0 1-2.2 2.2h-2.8a2.2 2.2 0 0 1-2.2-2.2z",
    ),
    "arrow-left" to listOf(
        "M14.5 5.5 8 12l6.5 6.5",
    ),
    "chevron-down" to listOf(
        "M7 10.2l5 5 5-5",
    ),
    "chevron-right" to listOf(
        "M10 7l5 5-5 5",
    ),
    "close" to listOf(
        "M6.6 6.6l10.8 10.8",
        "M17.4 6.6 6.6 17.4",
    ),
)

object MbIcons {
    val names: Set<String> get() = GLYPHS.keys

    /**
     * Path data is parsed once per glyph variant and kept.
     *
     * A list scroll rebuilds icons constantly; re-parsing the same strings on
     * every new composition is exactly the kind of small repeated cost that
     * reads as stutter.
     */
    private val cache = java.util.concurrent.ConcurrentHashMap<String, ImageVector>()

    fun vector(
        name: String,
        strokeWidth: Float = 1.6f,
        filled: Boolean = false,
    ): ImageVector = cache.getOrPut("$name|$strokeWidth|$filled") {
        val paths = GLYPHS[name] ?: GLYPHS.getValue("box")
        ImageVector.Builder(
            name = if (filled) "$name-filled" else name,
            defaultWidth = 24.dp,
            defaultHeight = 24.dp,
            viewportWidth = 24f,
            viewportHeight = 24f,
        ).apply {
            paths.forEach { data ->
                addPath(
                    pathData = addPathNodes(data),
                    // A filled glyph keeps its stroke too, so the silhouette
                    // stays the same size whether it is on or off.
                    fill = if (filled) SolidColor(Color.Black) else null,
                    stroke = SolidColor(Color.Black),
                    strokeLineWidth = strokeWidth,
                    strokeLineCap = StrokeCap.Round,
                    strokeLineJoin = StrokeJoin.Round,
                )
            }
        }.build()
    }
}

/**
 * Draws one glyph. [tint] recolours the stroke, which is why the vector itself
 * is built in black and tinted at draw time.
 */
@Composable
fun MbIcon(
    name: String,
    modifier: Modifier = Modifier,
    size: Dp = 20.dp,
    tint: Color = MbTheme.colors.ink,
    strokeWidth: Float = 1.6f,
    filled: Boolean = false,
) {
    val vector = remember(name, strokeWidth, filled) {
        MbIcons.vector(name, strokeWidth, filled)
    }
    Image(
        painter = rememberVectorPainter(vector),
        contentDescription = null,
        colorFilter = ColorFilter.tint(tint),
        modifier = modifier.size(size),
    )
}
