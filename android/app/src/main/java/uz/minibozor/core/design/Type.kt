package uz.minibozor.core.design

import androidx.compose.runtime.Immutable
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.LineHeightStyle
import androidx.compose.ui.unit.sp
import uz.minibozor.R

/**
 * The design is set in Plus Jakarta Sans, and now so is the app.
 *
 * It used to be [FontFamily.SansSerif], which on Android is Roboto — so every
 * style below was asking Roboto for weights and tracking that were measured on
 * a different face. The negative letter-spacing is the tell: it is there
 * because Jakarta's counters are open and its ExtraBold is wide, and applied to
 * Roboto it just made a tight face tighter.
 *
 * Five weights, static instances rather than the variable font: `Font(…,
 * variationSettings)` needs API 26 anyway and a static per weight is one
 * `Typeface` each with nothing to interpolate at draw time.
 *
 * The face covers Latin, Latin Extended and the punctuation this app sets —
 * `−` for a discount and `★` for a rating, both of which were checked rather
 * than assumed. It has no Cyrillic, so the Russian locale falls back to the
 * system face for its own alphabet; the numerals and the punctuation around
 * them stay Jakarta.
 */
val JakartaSans: FontFamily = FontFamily(
    Font(R.font.plus_jakarta_sans_regular, FontWeight.Normal),
    Font(R.font.plus_jakarta_sans_medium, FontWeight.Medium),
    Font(R.font.plus_jakarta_sans_semibold, FontWeight.SemiBold),
    Font(R.font.plus_jakarta_sans_bold, FontWeight.Bold),
    Font(R.font.plus_jakarta_sans_extrabold, FontWeight.ExtraBold),
)

private fun mb(
    size: Double,
    weight: FontWeight,
    tracking: Double = 0.0,
    lineHeight: Double = 1.3,
) = TextStyle(
    fontFamily = JakartaSans,
    fontSize = size.sp,
    fontWeight = weight,
    letterSpacing = tracking.sp,
    lineHeight = (size * lineHeight).sp,
    lineHeightStyle = LineHeightStyle(
        alignment = LineHeightStyle.Alignment.Center,
        trim = LineHeightStyle.Trim.None,
    ),
)

@Immutable
data class MbTypography(
    val display: TextStyle = mb(27.0, FontWeight.ExtraBold, -0.9, 1.16),
    val title1: TextStyle = mb(23.0, FontWeight.ExtraBold, -0.6, 1.15),
    val title2: TextStyle = mb(20.0, FontWeight.ExtraBold, -0.4, 1.2),
    val title3: TextStyle = mb(17.0, FontWeight.ExtraBold, -0.3, 1.25),
    val sectionHead: TextStyle = mb(15.5, FontWeight.ExtraBold, -0.2, 1.25),
    val price: TextStyle = mb(15.5, FontWeight.ExtraBold, -0.3, 1.2),
    val priceSmall: TextStyle = mb(14.0, FontWeight.ExtraBold, -0.3, 1.2),
    val statusBar: TextStyle = mb(14.5, FontWeight.Bold),
    val body: TextStyle = mb(13.0, FontWeight.Medium, 0.0, 1.45),
    val bodySmall: TextStyle = mb(12.5, FontWeight.Medium, 0.0, 1.6),
    val label: TextStyle = mb(11.5, FontWeight.Bold),
    val caption: TextStyle = mb(11.0, FontWeight.Medium, 0.0, 1.35),
    val captionBold: TextStyle = mb(11.0, FontWeight.Bold, 1.4),
    val meta: TextStyle = mb(10.5, FontWeight.Medium, 0.0, 1.35),
    val micro: TextStyle = mb(9.5, FontWeight.Bold),
    val badge: TextStyle = mb(8.5, FontWeight.ExtraBold, 1.2),
)

/** Struck-through "was" price. */
val MbTypography.strikePrice: TextStyle
    get() = meta.copy(fontSize = 10.sp)
