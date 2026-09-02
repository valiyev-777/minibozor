package uz.minibozor.core.design.component

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.ui.draw.shadow
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.wrapContentWidth
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil.compose.AsyncImage
import uz.minibozor.core.design.MbPressAlpha
import uz.minibozor.core.design.MbText
import uz.minibozor.core.design.MbTheme
import uz.minibozor.core.design.strikePrice
import uz.minibozor.core.design.mbPressDip
import uz.minibozor.core.design.mbPressIndication
import uz.minibozor.core.design.mbPressable
import uz.minibozor.core.design.mbTap
import uz.minibozor.core.design.rememberMbPress
import uz.minibozor.core.design.icon.MbIcon
import uz.minibozor.core.util.grouped
import uz.minibozor.core.util.mediaUrl
import uz.minibozor.core.util.sum

/** The soft ink wash a pressed tile is highlighted with. */
@Composable
private fun pressTint(): Color = MbTheme.colors.ink.copy(alpha = MbPressAlpha)

/**
 * The card's own ground: white on the light theme, a step off the page on the
 * dark one.
 *
 * `fill` rather than `surfaceAlt` on the dark theme. The card is separated by a
 * shadow on the light theme and by being lighter than its ground on the dark
 * one, where a shadow is invisible — and surfaceAlt is four values above the
 * panel the home page puts these cards on, which is not a step anybody can see.
 * `fill` is the palette's next stop up and reads against both grounds the cards
 * appear on.
 */
@Composable
private fun cardSurface(): Color =
    if (MbTheme.colors.isDark) MbTheme.colors.fill else MbTheme.colors.surface

/**
 * The card every product tile sits in: a soft surface, lifted a little, with
 * nothing drawn around it.
 *
 * Tiles used to be bare columns of photo, price and title separated by nothing
 * but a gap, which left the reader doing the grouping — two photos side by side
 * with four lines of text under them, and which price belongs to which shoe is
 * a guess. The first answer was a hairline box, and it worked, but eight boxes
 * in a grid is eight hard edges between the customer and the photographs; at
 * small sizes the border was the loudest thing in the tile.
 *
 * So the edge is gone and the lift does the grouping instead: a surface one step
 * off its ground with a 3 dp shadow under it, and a rounder corner than the
 * bordered version could carry. It reads on both grounds the tiles appear on —
 * the grey canvas of a listing and the white panel of the home page — and on
 * the dark theme, where a black shadow would be invisible, the card is a step
 * lighter than the page rather than lifted off it.
 *
 * The press is two things at once, from one interaction source so they start on
 * the same frame: the app's soft ink wash over the card, and the whole card
 * dipping under the finger.
 */
@Composable
private fun Modifier.productCard(
    onClick: () -> Unit,
    shape: Shape = MbTheme.shapes.tileLarge,
): Modifier {
    val press = rememberMbPress()
    val ink = MbTheme.colors.ink
    val lift = if (MbTheme.colors.isDark) 0.dp else MbTheme.dimens.cardLift
    return this
        // First in the chain, so the surface and its shadow dip with the
        // content instead of standing still around a shrinking photograph.
        .mbPressDip(press)
        .shadow(
            elevation = lift,
            shape = shape,
            // Clipped on the next line instead: shadow's own clip would also
            // clip the shadow away on the sides.
            clip = false,
            // The palette's own ink rather than flat black, softened — a
            // full-strength shadow under a 180 dp card reads as a dialogue
            // hovering over the page.
            ambientColor = ink.copy(alpha = 0.32f),
            spotColor = ink.copy(alpha = 0.40f),
        )
        .clip(shape)
        .background(cardSurface())
        // The wash is drawn over the content rather than clipping it, so the
        // second line of a title keeps every pixel.
        .clickable(
            interactionSource = press,
            indication = mbPressIndication(shape, pressTint()),
            onClick = onClick,
        )
}

/**
 * Photo with the design's warm neutral backdrop showing through while it loads.
 *
 * Fit, not Crop: catalogue photos are cut-outs of a whole product in mixed
 * aspect ratios, and cropping a 387x516 shoe into a square tile shows its
 * middle and cuts off the toe. Scene photography — the home banner — passes
 * Crop explicitly, which is what it wants.
 */
@Composable
fun MbProductImage(
    url: String?,
    modifier: Modifier = Modifier,
    shape: Shape = MbTheme.shapes.tile,
    /** The theme's photo ground unless overridden. */
    background: Color = Color.Unspecified,
    contentScale: ContentScale = ContentScale.Fit,
) {
    Box(
        modifier
            .clip(shape)
            .background(if (background == Color.Unspecified) MbTheme.colors.photoWarmAlt else background),
        contentAlignment = Alignment.Center,
    ) {
        val resolved = url.mediaUrl()
        if (resolved != null) {
            AsyncImage(
                model = resolved,
                contentDescription = null,
                // Whatever was uploaded, shown whole and filling its frame.
                // Cropping cut into the picture; insetting it left a ring of
                // ground around a photograph that came with its own backdrop,
                // which on the dark theme is a bright block with a dark border.
                contentScale = contentScale,
                modifier = Modifier.fillMaxSize(),
            )
        } else {
            // No photo yet. A muted glyph reads as "none supplied" where an
            // empty warm rectangle just reads as broken.
            MbIcon("box", size = 26.dp, tint = MbTheme.colors.hairlineStrong)
        }
    }
}

/**
 * The saving, in the red pill this app puts a discount in everywhere.
 *
 * One composable rather than the same six lines in three places — the tile, the
 * product page's own price and the bar at the top of it had drifted apart by a
 * padding already. The tracking is taken back out: `captionBold` is a label
 * style and carries 1.4 sp of it, which on a four-glyph token spaced `−9%` out
 * into `− 9 %` and read as three separate marks instead of one number.
 */
@Composable
fun MbDiscountPill(
    percent: Int,
    modifier: Modifier = Modifier,
    /** A step up for the product page, where the price is the largest thing. */
    large: Boolean = false,
) {
    MbText(
        "−$percent%",
        (if (large) MbTheme.type.label else MbTheme.type.captionBold)
            .copy(letterSpacing = 0.sp),
        MbTheme.colors.danger,
        modifier = modifier
            .clip(MbTheme.shapes.badge)
            .background(MbTheme.colors.dangerBg)
            .padding(
                horizontal = if (large) 9.dp else 6.dp,
                vertical = if (large) 5.dp else 3.dp,
            ),
        maxLines = 1,
    )
}

/**
 * What it costs, and what that is off: `1 090 000` on its own line, then
 * `1 540 000  −29%` under it.
 *
 * Two lines, not one. Beside the number the pill did not fit: a card in a
 * two-per-row grid has about 150 dp of text width, `168 000 000` takes 110 of
 * them at price weight, and the pill needs 40 more — so the two were pressed
 * against each other and on the longest prices the number itself was clipped.
 * They are also two different kinds of fact. What the thing costs is the
 * headline; what it used to cost and how much is off are the footnote, and a
 * footnote belongs under the line it annotates, at footnote size.
 */
@Composable
fun MbPriceRow(
    price: Int,
    oldPrice: Int? = null,
    discountPercent: Int? = null,
    modifier: Modifier = Modifier,
    priceStyle: TextStyle = MbTheme.type.price,
) {
    val was = oldPrice?.takeIf { it > price }
    Column(modifier) {
        MbText(price.grouped(), priceStyle, maxLines = 1)
        Spacer(Modifier.height(3.dp))
        // The footnote line is always there, even with nothing to say.
        //
        // A grid lays two cards side by side and neither stretches to the
        // other, so a discounted product next to a full-price one left one
        // card's bottom edge a line higher than its neighbour's. Holding the
        // room keeps every card in a row the same height. A minimum rather
        // than a fixed height, so the pill still has somewhere to go when the
        // customer has turned their font size up.
        Row(
            Modifier.defaultMinSize(minHeight = 20.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            if (was != null) {
                MbText(
                    was.grouped(),
                    MbTheme.type.strikePrice
                        .copy(textDecoration = TextDecoration.LineThrough),
                    MbTheme.colors.textQuaternary,
                    maxLines = 1,
                )
            }
            // A pill rather than 9.5sp of red text: the saving is the reason
            // someone stops on the card, and it was the smallest thing on it.
            if (discountPercent != null) MbDiscountPill(discountPercent)
        }
    }
}

@Composable
fun MbStars(rating: Int, modifier: Modifier = Modifier, size: Dp = 13.dp) {
    Row(modifier, horizontalArrangement = Arrangement.spacedBy(1.dp)) {
        repeat(5) { index ->
            MbText(
                "★",
                MbTheme.type.caption.copy(fontSize = size.value.sp),
                if (index < rating) MbTheme.colors.star else MbTheme.colors.divider,
            )
        }
    }
}

/**
 * The same five stars, but a 4.3 shows four gold and a third of the fifth.
 *
 * Rounding to four stars loses the very thing the number is for — the
 * difference between a 4.0 and a 4.4 is most of what a rating says — so the
 * partial star is drawn by clipping a gold glyph over a grey one. The cell is
 * given the glyph's own width so the fraction lands where the eye expects it.
 */
@Composable
fun MbStars(rating: Double, modifier: Modifier = Modifier, size: Dp = 15.dp) {
    val style = MbTheme.type.caption.copy(fontSize = size.value.sp)
    // The glyph is drawn a touch narrower than its point size; measured once
    // here rather than guessed per call site.
    val cell = size * 1.06f
    Row(modifier, horizontalArrangement = Arrangement.spacedBy(size * 0.1f)) {
        repeat(5) { index ->
            val fill = (rating - index).coerceIn(0.0, 1.0).toFloat()
            Box(Modifier.width(cell)) {
                MbText("★", style, MbTheme.colors.divider)
                if (fill > 0f) {
                    Box(Modifier.width(cell * fill).clipToBounds()) {
                        MbText(
                            "★",
                            style,
                            MbTheme.colors.star,
                            // Unbounded, so clipping takes the right-hand side
                            // of the star off rather than squeezing the glyph
                            // into the box.
                            modifier = Modifier.wrapContentWidth(
                                align = Alignment.Start,
                                unbounded = true,
                            ),
                        )
                    }
                }
            }
        }
    }
}

/**
 * The price as the product page opens with it: the number at full size, the
 * saving beside it in the pill this app puts a discount in everywhere else, and
 * what it used to cost struck through underneath.
 *
 * Separate from [MbPriceRow], which is the tile's version — a 15 sp number in a
 * row of other 15 sp numbers. Here the price is the reason the page exists, so
 * it is the largest thing on it. The idiom is ours and deliberately so: a red
 * pill on a tinted ground, the same one the grid tiles and the cart use, rather
 * than a coloured arrow and a word of explanation borrowed from somebody else's
 * shop.
 */
@Composable
fun MbHeroPrice(
    price: Int,
    oldPrice: Int? = null,
    discountPercent: Int? = null,
    /**
     * A step smaller, for the bar at the top of the product page.
     *
     * The bar carries the same price the panel does — it is the panel's job once
     * the panel has scrolled away — but it also carries the product's name above
     * it and a status bar over that, so the full 27 sp would make the bar a
     * third of the screen.
     */
    compact: Boolean = false,
    modifier: Modifier = Modifier,
) {
    Column(modifier) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(if (compact) 8.dp else 10.dp),
        ) {
            MbText(
                price.sum(),
                if (compact) MbTheme.type.title1 else MbTheme.type.display,
                maxLines = 1,
            )
            if (discountPercent != null) {
                MbDiscountPill(discountPercent, large = !compact)
            }
        }
        if (oldPrice != null && oldPrice > price) {
            Spacer(Modifier.height(if (compact) 1.dp else 3.dp))
            MbText(
                oldPrice.grouped(),
                (if (compact) MbTheme.type.caption else MbTheme.type.sectionHead)
                    .copy(textDecoration = TextDecoration.LineThrough),
                MbTheme.colors.textQuaternary,
                maxLines = 1,
            )
        }
    }
}

/**
 * The overlapping strip of customer photographs beside a rating.
 *
 * The last tile carries "+N" for everything the strip has no room for, which is
 * also the tap target's promise: there are more of these, and they are through
 * here. Drawn overlapping rather than spaced, so three tiles read as a stack of
 * many rather than as three separate pictures.
 */
@Composable
fun MbReviewPhotoStack(
    photos: List<String>,
    total: Int,
    modifier: Modifier = Modifier,
    tile: Dp = 46.dp,
    shown: Int = 3,
) {
    if (photos.isEmpty()) return
    val strip = photos.take(shown)
    val more = total - strip.size
    Row(modifier, horizontalArrangement = Arrangement.spacedBy(-tile * 0.22f)) {
        strip.forEachIndexed { index, photo ->
            Box(
                Modifier
                    .size(tile)
                    // A ring of the panel's own surface, so the tiles read as
                    // separate cards where they overlap.
                    .clip(MbTheme.shapes.tileSmall)
                    .background(MbTheme.colors.surface)
                    .padding(1.5.dp)
            ) {
                MbProductImage(
                    photo,
                    modifier = Modifier.fillMaxSize(),
                    shape = MbTheme.shapes.badge,
                    contentScale = ContentScale.Crop,
                )
                if (index == strip.lastIndex && more > 0) {
                    Box(
                        Modifier
                            .fillMaxSize()
                            .clip(MbTheme.shapes.badge)
                            .background(MbTheme.colors.scrim),
                        contentAlignment = Alignment.Center,
                    ) {
                        MbText("+$more", MbTheme.type.label, MbTheme.colors.onScrim)
                    }
                }
            }
        }
    }
}

/**
 * Add to cart, at the end of the card's own last line.
 *
 * It has been three things. A full-width blue bar across the foot of every card
 * — a lot of blue in a grid of eight, and a whole row of card height spent on
 * the secondary action, the primary one being to open the product. Then a disc
 * punched into the corner of the photograph, which was handy and looked like a
 * sticker somebody had put on the picture. This is the third: a plain accent
 * disc beside the name, sharing the two lines the name already occupies, so it
 * costs the card no height at all and sits on the card's own surface rather
 * than on the seller's photograph.
 *
 * No flourish on it. The feedback is the same dip every card in the app makes
 * under a finger, and nothing else — a swelling ring or a glyph that flips to a
 * tick would be claiming more than the tap knows, since on a product with sizes
 * it opens the picker instead of adding anything.
 */
@Composable
fun MbCartButton(
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    size: Dp = 34.dp,
    /** Transparent room around the disc, part of the tap target. */
    margin: Dp = 5.dp,
) {
    val press = rememberMbPress()
    Box(
        modifier
            .size(size + margin * 2)
            .clickable(
                interactionSource = press,
                // The disc dips instead; a ripple in the box around it would be
                // a second, larger answer to the same tap.
                indication = null,
                onClick = onClick,
            ),
        contentAlignment = Alignment.Center,
    ) {
        Box(
            Modifier
                .mbPressDip(press, pressedScale = 0.9f)
                .size(size)
                .clip(CircleShape)
                .background(MbTheme.colors.accent),
            contentAlignment = Alignment.Center,
        ) {
            MbIcon("cart", size = size * 0.47f, tint = Color.White, strokeWidth = 2f)
        }
    }
}

/**
 * The two-per-row grid tile from the home screen and search results: a square
 * photograph with the heart in one corner and the cart in the other, then the
 * price, then the name.
 *
 * Both corner controls are optional, and [MbDealTile] is this same card with
 * neither — the two used to be separate copies of the same column and had
 * already drifted by a gap and a text style.
 */
@Composable
fun MbProductTile(
    title: String,
    price: Int,
    oldPrice: Int?,
    discountPercent: Int?,
    imageUrl: String?,
    isFavorite: Boolean,
    onClick: () -> Unit,
    onToggleFavorite: () -> Unit,
    onAddToCart: (() -> Unit)? = null,
    modifier: Modifier = Modifier,
) {
    ProductTileBody(
        title = title,
        price = price,
        oldPrice = oldPrice,
        discountPercent = discountPercent,
        imageUrl = imageUrl,
        isFavorite = isFavorite,
        onClick = onClick,
        onToggleFavorite = onToggleFavorite,
        onAddToCart = onAddToCart,
        modifier = modifier,
    )
}

/** Wide "Bugungi tanlov" tile: the same card without the rating or the toggles. */
@Composable
fun MbDealTile(
    title: String,
    price: Int,
    oldPrice: Int?,
    discountPercent: Int?,
    imageUrl: String?,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    ProductTileBody(
        title = title,
        price = price,
        oldPrice = oldPrice,
        discountPercent = discountPercent,
        imageUrl = imageUrl,
        isFavorite = false,
        onClick = onClick,
        onToggleFavorite = null,
        onAddToCart = null,
        modifier = modifier,
    )
}

/**
 * The card itself: a square photograph, then what it costs, then what it is.
 *
 * Three things, and nothing else.
 *
 * The order is deliberate and it is the order a shopper reads a grid in — the
 * picture stops them, the number decides them, the name confirms it. So the
 * number is the heaviest thing in the text block and the name is set at reading
 * size under it.
 *
 * Explicit gaps rather than one blanket spacing: the photograph wants room under
 * it, and the lines under that belong to each other and read as a block only if
 * they are closer to one another than to the picture. A single `spacedBy` could
 * not say that.
 */
@Composable
private fun ProductTileBody(
    title: String,
    price: Int,
    oldPrice: Int?,
    discountPercent: Int?,
    imageUrl: String?,
    isFavorite: Boolean,
    onClick: () -> Unit,
    /** Null leaves the heart off the photograph. */
    onToggleFavorite: (() -> Unit)?,
    onAddToCart: (() -> Unit)?,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier
            .productCard(onClick = onClick)
            .padding(8.dp),
    ) {
        Box {
            MbProductImage(
                imageUrl,
                modifier = Modifier
                    // Square, like the rail tiles: the catalogue photos are
                    // 1:1 with their own baked-in backdrop, so a letterboxed
                    // strip of tile shows through any other ratio.
                    .fillMaxWidth()
                    .aspectRatio(1f),
                shape = MbTheme.shapes.tileSmall,
            )
            if (onToggleFavorite != null) {
                FavoriteBubble(
                    isFavorite = isFavorite,
                    onClick = onToggleFavorite,
                    // No padding of its own: the bubble carries a transparent
                    // margin that is part of its tap target, so the heart sits
                    // where it always did while being twice as easy to hit.
                    modifier = Modifier.align(Alignment.TopEnd),
                )
            }
        }
        Spacer(Modifier.height(9.dp))
        // Full width, always: the price is the one line on the card that must
        // never be squeezed, so nothing shares its row.
        MbPriceRow(price, oldPrice, discountPercent)
        Spacer(Modifier.height(6.dp))
        // Two lines always, so every tile in a row is the same height and no
        // title ends up pressed against the card edge. Longer than that is cut
        // with an ellipsis rather than allowed to push the price of the tile
        // beside it out of line.
        //
        // Set at reading size, not at 11 sp. A product name in a two-up grid is
        // the one thing on the card that has to be read rather than recognised —
        // "Nike Air Force 1 '07, oq-pushti" is four facts, and at caption size
        // next to a 15.5 sp price it was being skipped.
        // The last line on the card, and deliberately: no rating, no review
        // count. A star and "12 sharh" on every tile of a grid is a row of
        // numbers nobody compares — what a rating is for is the product page,
        // where there is a panel of them and the reviews themselves are a tap
        // away. The card is a picture, a price and a name.
        //
        // The cart shares this block rather than getting a row of its own: the
        // name is always two lines, which is exactly the room the disc needs, so
        // the action costs the card nothing. A name long enough to reach the
        // disc ends in an ellipsis, which it did anyway.
        Row(verticalAlignment = Alignment.CenterVertically) {
            MbText(
                title,
                MbTheme.type.body,
                MbTheme.colors.inkSoft,
                maxLines = 2,
                minLines = 2,
                modifier = Modifier.weight(1f),
            )
            if (onAddToCart != null) {
                Spacer(Modifier.width(4.dp))
                MbCartButton(onAddToCart)
            }
        }
    }
}

/** The 112 dp tile used by the horizontal rails ("Poyabzal", "Elektronika"). */
@Composable
fun MbRailTile(
    title: String,
    price: Int,
    discountPercent: Int?,
    imageUrl: String?,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier
            .width(MbTheme.dimens.railTileWidth)
            // A step less round than the grid tile: the same 18 dp corner on a
            // 112 dp card is half its width in arcs.
            .productCard(onClick = onClick, shape = MbTheme.shapes.tile)
            .padding(7.dp),
    ) {
        MbProductImage(
            imageUrl,
            modifier = Modifier
                .fillMaxWidth()
                .aspectRatio(1f),
            shape = MbTheme.shapes.tileSmall,
            background = MbTheme.colors.photoWarm,
        )
        Spacer(Modifier.height(8.dp))
        // The same block the grid tile uses, a size down. It used to be a row of
        // its own making — the price and 9.5 sp of red text side by side — which
        // on a 112 dp card meant a nine-figure price and a percentage fighting
        // over 98 dp, and the price losing its last digits.
        MbPriceRow(
            price = price,
            discountPercent = discountPercent,
            priceStyle = MbTheme.type.priceSmall,
        )
        Spacer(Modifier.height(4.dp))
        // A step up from meta: the rail is 112 dp wide, so a name gets two short
        // lines and needs every one of them to be readable.
        MbText(title, MbTheme.type.caption, MbTheme.colors.inkSoft, maxLines = 2, minLines = 2)
    }
}

/**
 * The heart on a photograph.
 *
 * [size] is the disc that is seen; [margin] is transparent room around it that
 * belongs to the tap target, so a 28 dp bubble is a 44 dp thing to hit. It used
 * to be a bare 24 dp circle with 6 dp of padding outside it — a target smaller
 * than a fingertip, sitting in the corner of a card that is itself tappable, so
 * a miss opened the product instead of saving it.
 *
 * The disc is white with a hairline of ink under it rather than plain white at
 * 92%: half the catalogue is photographed against a pale studio backdrop, and a
 * white circle on off-white had to be looked for.
 */
@Composable
fun FavoriteBubble(
    isFavorite: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    size: Dp = 28.dp,
    margin: Dp = 8.dp,
) {
    // Nothing on the dark theme: the palette's ink is a near-white there, so a
    // shadow drawn in it is a pale halo around the disc rather than a lift under
    // it — and a white disc on a dark page needs no help being seen.
    val lift = if (MbTheme.colors.isDark) 0.dp else 2.dp
    Box(
        modifier
            .size(size + margin * 2)
            .clip(CircleShape)
            .mbTap(onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        Box(
            Modifier
                .size(size)
                // Under the clip, so the lift is a disc and not a square.
                .shadow(lift, CircleShape, clip = false, spotColor = MbTheme.colors.ink)
                .clip(CircleShape)
                .background(Color.White),
            contentAlignment = Alignment.Center,
        ) {
            MbIcon(
                "heart",
                size = size * 0.5f,
                tint = if (isFavorite) MbTheme.colors.danger else MbTheme.colors.textSecondary,
                strokeWidth = 2f,
                filled = isFavorite,
            )
        }
    }
}

/** Compact line item: photo, title, variant, price — cart, orders, reviews. */
@Composable
fun MbLineItem(
    title: String,
    imageUrl: String?,
    meta: String,
    price: Int,
    quantity: Int? = null,
    modifier: Modifier = Modifier,
    onClick: (() -> Unit)? = null,
    trailing: @Composable (() -> Unit)? = null,
) {
    Row(
        modifier
            .fillMaxWidth()
            // Pressed in the row's own rounded shape rather than as a bare
            // rectangle across the panel: mbPressable draws the highlight over
            // the content, so the photo and the last line of the title keep
            // every pixel.
            .let {
                if (onClick != null) {
                    it.mbPressable(MbTheme.shapes.tile, pressTint(), onClick = onClick)
                } else {
                    it
                }
            },
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        MbProductImage(
            imageUrl,
            modifier = Modifier.size(64.dp),
            shape = MbTheme.shapes.tileSmall,
        )
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
            MbText(title, MbTheme.type.caption, MbTheme.colors.inkSoft, maxLines = 2)
            if (meta.isNotBlank()) {
                MbText(meta, MbTheme.type.meta, MbTheme.colors.icon, maxLines = 1)
            }
            Row(verticalAlignment = Alignment.CenterVertically) {
                MbText(price.grouped(), MbTheme.type.priceSmall)
                if (quantity != null) {
                    MbText(
                        "  × $quantity",
                        MbTheme.type.meta,
                        MbTheme.colors.icon,
                    )
                }
            }
        }
        trailing?.invoke()
    }
}
