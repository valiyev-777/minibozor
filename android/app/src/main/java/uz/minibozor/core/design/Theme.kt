package uz.minibozor.core.design

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material.ripple.RippleAlpha
import androidx.compose.material3.LocalRippleConfiguration
import androidx.compose.material3.RippleConfiguration
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.LocalTextStyle
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.darkColorScheme
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
 * The design ships a single light appearance; [MbColors.dark] derives the dark
 * one from it. The palette follows the system setting, which is also what the
 * "Tungi rejim" row on screen 37 describes ("Tizim bilan moslashadi").
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MiniBozorTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    val colors = if (darkTheme) MbColors.dark() else MbColors()
    val typography = MbTypography()

    CompositionLocalProvider(
        LocalMbColors provides colors,
        // Material's own ripple takes its colour from the content colour, which
        // on a light theme is near-black — a tap on a white card flashed a dark
        // disc across it. Same hue, a twentieth of the strength, and it inverts
        // with the palette so a dark theme gets a pale one instead.
        LocalRippleConfiguration provides RippleConfiguration(
            color = colors.ink,
            rippleAlpha = RippleAlpha(
                draggedAlpha = MbPressAlpha,
                focusedAlpha = MbPressAlpha,
                hoveredAlpha = MbPressAlpha * 0.6f,
                pressedAlpha = MbPressAlpha,
            ),
        ),
        LocalMbTypography provides typography,
        LocalMbDimens provides MbDimens(),
        LocalMbShapes provides MbShapes(),
        LocalTextStyle provides typography.body.copy(color = colors.ink),
    ) {
        val scheme = if (darkTheme) {
            darkColorScheme(
                primary = colors.accent,
                onPrimary = Color.White,
                background = colors.canvas,
                onBackground = colors.ink,
                surface = colors.surface,
                onSurface = colors.ink,
                surfaceContainerLow = colors.surface,
                error = colors.danger,
            )
        } else {
            lightColorScheme(
                primary = colors.accent,
                onPrimary = Color.White,
                background = colors.canvas,
                onBackground = colors.ink,
                surface = colors.surface,
                onSurface = colors.ink,
                error = colors.danger,
            )
        }
        MaterialTheme(colorScheme = scheme, content = content)
    }
}

/** Text with the design's styles, so screens never touch MaterialTheme.typography. */
@Composable
fun MbText(
    text: String,
    style: TextStyle,
    color: Color = MbTheme.colors.ink,
    maxLines: Int = Int.MAX_VALUE,
    minLines: Int = 1,
    modifier: androidx.compose.ui.Modifier = androidx.compose.ui.Modifier,
    overflow: androidx.compose.ui.text.style.TextOverflow =
        androidx.compose.ui.text.style.TextOverflow.Ellipsis,
    textAlign: androidx.compose.ui.text.style.TextAlign? = null,
    /** Lets a caller find out whether the text was actually clipped. */
    onTextLayout: ((androidx.compose.ui.text.TextLayoutResult) -> Unit)? = null,
) {
    Text(
        text = text,
        style = style,
        color = color,
        maxLines = maxLines,
        minLines = minLines,
        overflow = overflow,
        textAlign = textAlign,
        onTextLayout = onTextLayout ?: {},
        modifier = modifier,
    )
}
