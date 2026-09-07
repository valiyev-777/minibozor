package uz.minibozor.core.design

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.Immutable
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp

/**
 * Spacing, radii and component metrics from `design/tokens.json`.
 *
 * The design is drawn at 375 dp wide, which is close enough to a real phone that
 * these values are used as-is rather than scaled.
 */
/** The page edge every home block keeps, cards included. */
private val HomeEdge = 16.dp

/** The gap between two cards standing side by side. */
private val CardGap = 12.dp

/**
 * How wide a product card is — the same number for a grid tile and a rail tile.
 *
 * The home page used to draw three different cards. The grid gave each tile
 * half the page, the deals pair gave each of two tiles half a panel inside the
 * page, and a rail tile was a hard 112 dp derived to show two and a half of
 * them — a card two thirds the width of the one above it, carrying a name at
 * caption size next to a price at small size. Three widths and three type
 * scales down one scroll, which reads as three different kinds of thing rather
 * than as one shop's shelves.
 *
 * So there is one width, and the grid's is what it is: half the page less its
 * edges and the gap down the middle. A rail then shows two cards and the start
 * of a third, which is a rail saying it continues — the same thing the half
 * card said, at a size the card's own contents can actually be read at.
 */
@Composable
fun rememberProductCardWidth(): Dp {
    val screen = LocalConfiguration.current.screenWidthDp.dp
    // A floor rather than a ceiling: a narrow phone still gets a card wide
    // enough for the price and the cart disc to share the last line.
    return ((screen - HomeEdge * 2 - CardGap) / 2).coerceAtLeast(120.dp)
}

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
    /**
     * 44, not 38. Search is the one thing on the home page that is reached for
     * at any depth of the feed, and 38 dp is under what a fingertip is reliably
     * given — it also read as a thin grey slot rather than a field once it was
     * the only thing left at the top of a scrolled page.
     */
    val searchHeight: Dp = 44.dp,
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
     * How wide one product card is.
     *
     * The only metric here that cannot be drawn once at 375 dp and used as-is.
     * See [rememberProductCardWidth], which is what the theme actually puts
     * here; this default is for previews and tests.
     */
    val productCardWidth: Dp = 164.dp,
    /** The page edge every block of the home feed keeps. */
    val homeEdge: Dp = HomeEdge,
    /** The gap between two cards standing side by side. */
    val cardGap: Dp = CardGap,
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
