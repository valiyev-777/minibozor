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
    /**
     * Tall enough for the panel's own content: kicker, two lines of title, a
     * line of subtitle and the button under them come to about 123 dp, which
     * did not fit inside 146 dp less its padding — the button lost its bottom.
     */
    val bannerHeight: Dp = 162.dp,
    val tabBarHeight: Dp = 74.dp,
    val tabBarInset: Dp = 14.dp,
    /** Gap below the floating bar, per the design. */
    val tabBarBottom: Dp = 16.dp,
    /**
     * Lifted clear of the gesture handle by this much on top of whatever the
     * system asks for. Added rather than folded into [tabBarBottom] so it
     * still applies on a three-button device, where the system inset is the
     * larger of the two and would otherwise swallow it.
     */
    val tabBarLift: Dp = 8.dp,

    /**
     * 112, not 100: the rail tile is a bounded card now, and its 6 dp of inner
     * padding came out of the photograph. This keeps the picture the size it
     * always was and puts the card's edge outside it.
     */
    val railTileWidth: Dp = 112.dp,
    val categoryTile: Dp = 44.dp,

    /**
     * How far a product card is lifted off whatever it sits on.
     *
     * The cards used to be drawn with a hairline around them, which on a grid of
     * eight tiles is eight boxes the eye has to read past to get to the
     * photographs. A shadow groups a card just as plainly and draws nothing:
     * 3 dp is enough to separate a white card from the grey canvas of a listing
     * and from the white panel of the home page alike, and shallow enough not to
     * look like a floating dialogue.
     *
     * On the dark theme it is dropped to nothing — a black shadow on a near
     * black canvas is invisible, and the card is separated by being a step
     * lighter than its ground instead.
     */
    val cardLift: Dp = 3.dp,
)

@Immutable
data class MbShapes(
    val card: RoundedCornerShape = RoundedCornerShape(20.dp),
    val tile: RoundedCornerShape = RoundedCornerShape(14.dp),
    /**
     * The product card's own corner, a step rounder than [tile].
     *
     * Rounder reads as softer, which is the point of losing the border: 18 dp
     * against the tile's 14 keeps the photograph inside it concentric at the
     * card's 8 dp of padding.
     */
    val tileLarge: RoundedCornerShape = RoundedCornerShape(18.dp),
    val tileSmall: RoundedCornerShape = RoundedCornerShape(13.dp),
    val field: RoundedCornerShape = RoundedCornerShape(12.dp),
    val button: RoundedCornerShape = RoundedCornerShape(14.dp),
    val chip: RoundedCornerShape = RoundedCornerShape(999.dp),
    val badge: RoundedCornerShape = RoundedCornerShape(6.dp),
    val sheet: RoundedCornerShape = RoundedCornerShape(topStart = 24.dp, topEnd = 24.dp),
    val tabBar: RoundedCornerShape = RoundedCornerShape(24.dp),
)
