package uz.minibozor.core.design

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Immutable
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp

/**
 * Spacing, radii and component metrics from `design/tokens.json`.
 *
 * The design is drawn at 375 dp wide, which is close enough to a real phone that
 * these values are used as-is rather than scaled.
 */
@Immutable
data class MbDimens(
    val gutter: Dp = 20.dp,
    val cardGutter: Dp = 12.dp,
    val cardPad: Dp = 14.dp,
    val sectionPad: Dp = 16.dp,

    val gapXs: Dp = 4.dp,
    val gapSm: Dp = 6.dp,
    val gapMd: Dp = 10.dp,
    val gapLg: Dp = 12.dp,
    val gapXl: Dp = 16.dp,

    val radiusXs: Dp = 6.dp,
    val radiusSm: Dp = 8.dp,
    val radiusMd: Dp = 12.dp,
    val radiusLg: Dp = 13.dp,
    val radiusXl: Dp = 14.dp,
    val radiusXxl: Dp = 20.dp,

    val buttonHeight: Dp = 48.dp,
    val fieldHeight: Dp = 48.dp,
    val searchHeight: Dp = 38.dp,
    val bannerHeight: Dp = 146.dp,
    val tabBarHeight: Dp = 84.dp,
    val tabBarInset: Dp = 14.dp,
    /** Gap below the floating bar, per the design. */
    val tabBarBottom: Dp = 16.dp,

    val railTileWidth: Dp = 100.dp,
    val categoryTile: Dp = 44.dp,
)

@Immutable
data class MbShapes(
    val card: RoundedCornerShape = RoundedCornerShape(20.dp),
    val tile: RoundedCornerShape = RoundedCornerShape(14.dp),
    val tileSmall: RoundedCornerShape = RoundedCornerShape(13.dp),
    val field: RoundedCornerShape = RoundedCornerShape(12.dp),
    val button: RoundedCornerShape = RoundedCornerShape(14.dp),
    val chip: RoundedCornerShape = RoundedCornerShape(999.dp),
    val badge: RoundedCornerShape = RoundedCornerShape(6.dp),
    val sheet: RoundedCornerShape = RoundedCornerShape(topStart = 24.dp, topEnd = 24.dp),
    val tabBar: RoundedCornerShape = RoundedCornerShape(24.dp),
)
