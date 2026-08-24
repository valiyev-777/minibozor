package uz.minibozor.core.design

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.LocalTextStyle
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.ReadOnlyComposable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle

private val LocalMbColors = staticCompositionLocalOf { MbColors() }
private val LocalMbTypography = staticCompositionLocalOf { MbTypography() }
private val LocalMbDimens = staticCompositionLocalOf { MbDimens() }
private val LocalMbShapes = staticCompositionLocalOf { MbShapes() }

object MbTheme {
    val colors: MbColors
        @Composable @ReadOnlyComposable get() = LocalMbColors.current
    val type: MbTypography
        @Composable @ReadOnlyComposable get() = LocalMbTypography.current
    val dimens: MbDimens
        @Composable @ReadOnlyComposable get() = LocalMbDimens.current
    val shapes: MbShapes
        @Composable @ReadOnlyComposable get() = LocalMbShapes.current
}

/**
 * The design ships a single light appearance. [darkTheme] is accepted so the
 * "Tungi rejim" switch on screen 37 has something to drive later, but for now it
 * intentionally renders the same palette rather than inventing colours the
 * design never specified.
 */
@Composable
fun MiniBozorTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    val colors = MbColors()
    val typography = MbTypography()

    CompositionLocalProvider(
        LocalMbColors provides colors,
        LocalMbTypography provides typography,
        LocalMbDimens provides MbDimens(),
        LocalMbShapes provides MbShapes(),
        LocalTextStyle provides typography.body.copy(color = colors.ink),
    ) {
        MaterialTheme(
            colorScheme = lightColorScheme(
                primary = colors.accent,
                onPrimary = Color.White,
                background = colors.canvas,
                onBackground = colors.ink,
                surface = colors.surface,
                onSurface = colors.ink,
                error = colors.danger,
            ),
            content = content,
        )
    }
}

/** Text with the design's styles, so screens never touch MaterialTheme.typography. */
@Composable
fun MbText(
    text: String,
    style: TextStyle,
    color: Color = MbTheme.colors.ink,
    maxLines: Int = Int.MAX_VALUE,
    modifier: androidx.compose.ui.Modifier = androidx.compose.ui.Modifier,
    overflow: androidx.compose.ui.text.style.TextOverflow =
        androidx.compose.ui.text.style.TextOverflow.Ellipsis,
    textAlign: androidx.compose.ui.text.style.TextAlign? = null,
) {
    Text(
        text = text,
        style = style,
        color = color,
        maxLines = maxLines,
        overflow = overflow,
        textAlign = textAlign,
        modifier = modifier,
    )
}
