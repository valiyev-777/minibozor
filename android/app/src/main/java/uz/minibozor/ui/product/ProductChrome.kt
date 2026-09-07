package uz.minibozor.ui.product

import android.content.Context
import android.content.Intent
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.animateDpAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.PagerState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.RectangleShape
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.layout.LayoutCoordinates
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.layout.positionInRoot
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.toSize
import uz.minibozor.R
import uz.minibozor.core.design.MbText
import uz.minibozor.core.design.MbTheme
import uz.minibozor.core.design.component.MbChip
import uz.minibozor.core.design.component.MbPrimaryButton
import uz.minibozor.core.design.component.MbProductImage
import uz.minibozor.core.design.component.MbQuantityStepper
import uz.minibozor.core.design.component.StockLine
import uz.minibozor.core.design.component.MbRailTile
import uz.minibozor.core.design.component.MbSkeleton
import uz.minibozor.core.design.component.SectionHeader
import uz.minibozor.core.design.icon.MbIcon
import uz.minibozor.core.design.mbPressable
import uz.minibozor.core.design.mbTap
import uz.minibozor.data.remote.dto.CartItemDto
import uz.minibozor.data.remote.dto.ProductCardDto
import uz.minibozor.data.remote.dto.ProductDto

/**
 * The photo frame: square, matching the photographs.
 *
 * A frame taller than the photo is wide leaves a band of frame down each side
 * of a fitted picture, and two near-identical lights with a seam between them
 * read as a mistake rather than a margin. Every catalogue photo is 1:1, so a
 * square frame has nothing left over to show — and it is short enough that the
 * price bar stays on screen with it.
 */
@Composable
fun heroHeight(): Dp = LocalConfiguration.current.screenWidthDp.dp

/**
 * How opaque the bar's own surface is, for a given crossing of the page under it.
 *
 * Shared with the screen, which hands the system's bar icons back to the theme
 * at the moment this reaches 1. Before that they are held light, because what
 * is behind them is the wash over the photograph.
 */
fun barCover(crossing: Float): Float = (crossing * 8f).coerceAtMost(1f)

/**
 * The bar: the status bar inset plus the row of buttons under it.
 *
 * 74 dp is the row itself — a 46 dp button with 18 dp of air above it and 10 dp
 * below. The air above used to be 10 as well, which on a phone whose status bar
 * carries a row of icons put the share button 15 dp under the battery: not
 * touching it, but close enough that the two read as one cluttered strip, and
 * the wash the buttons sit on runs between them so there is no edge to separate
 * them either. The extra 8 dp is what makes the buttons the app's and the icons
 * the phone's.
 *
 * Shared with the screen, which decides when the page has crossed under the bar
 * off the same number; hard-coding 56 in both drifted the moment the buttons
 * grew.
 */
val ChromeRowHeight: Dp = 74.dp

/**
 * The status bar's height, held at the tallest this window has ever reported.
 *
 * Reading the live inset was enough until the share sheet: MIUI opens it as its
 * own window over the page, the page stops being the focused one, and while it
 * is not, the status bar inset it is handed comes back as nothing. The bar's
 * padding collapsed with it and the three buttons jumped up under the clock —
 * behind the sheet, so what the customer saw was the row moving on its own and
 * moving back a moment later.
 *
 * A held maximum rather than the live figure: whatever the system says while
 * another window has the focus, this page still has a status bar above it and
 * has to keep its distance from it. It only ever grows, which on a phone held
 * in portrait is the whole of the story.
 */
@Composable
fun statusBarTop(): Dp {
    val live = WindowInsets.statusBars.asPaddingValues().calculateTopPadding()
    var held by remember { mutableStateOf(live) }
    if (live > held) held = live
    return held
}

@Composable
fun chromeHeight(): Dp = statusBarTop() + ChromeRowHeight

/** A stable key for the recommendations row. */
const val RecommendationsKey = "recommendations"

/**
 * The photo, edge to edge and under the status bar.
 *
 * As the page scrolls it does not simply slide away: it holds back at a third
 * of the scroll, fades, and settles slightly smaller, so it reads as closing
 * behind the content rather than being pushed off the top.
 */
@Composable
fun Hero(
    images: List<String>,
    closed: () -> Float,
    /** Hoisted, so the bar above shares the page the photo is showing. */
    pager: PagerState,
    /**
     * Pixels the photo hangs back from the scroll.
     *
     * The list moves everything up together; holding the photo back by a
     * fraction of that lets the page's own panels climb over it, which is what
     * puts them plainly in front rather than merely after it. Applied to the
     * whole frame, ground included, or the picture would slide out of its own
     * backdrop.
     */
    lag: () -> Float,
    /**
     * Tapping the photograph opens it full screen, out of the bounds it hands
     * over here — read at the moment of the tap rather than at layout time, so
     * a picture that has been scrolled (and holds back behind the page as it
     * goes) flies from where it actually is.
     */
    onOpen: (Rect) -> Unit,
) {
    // Two boxes, and the clip between them is the point. The outer one keeps
    // the frame's own bounds and scrolls with the list; the inner one holds
    // back. Held back without the clip the picture reaches past the panel in
    // front of it and turns up again in the seams between the panels below,
    // sliding about in them. Clipped, it can only ever be seen in the band the
    // panel has not yet reached.
    Box(
        Modifier
            .fillMaxWidth()
            .height(heroHeight())
            .clipToBounds()
    ) {
        Box(
            Modifier
                .fillMaxSize()
                // Read in the layer phase: following the scroll this way costs
                // no recomposition, only a new transform.
                //
                // Nothing fades here. Fading it left the top of the screen
                // showing the page's own ground through a transparent
                // photograph — a white band on the light theme, for the whole
                // time the frame was still on screen and not yet covered. It
                // leaves by being covered, which is opaque the entire way.
                .graphicsLayer { translationY = lag() }
                // The theme's photo ground, the same one the grid tiles use.
                .background(MbTheme.colors.photoStudio)
        ) {
        // The whole frame, the strip behind the bar included. The frame used to
        // be a square of photograph plus the bar's height, which left a band of
        // plain ground across the top; the picture reaches the top of the
        // screen now and the bar sits on it.
        HorizontalPager(
            pager,
            Modifier
                .fillMaxWidth()
                .aspectRatio(1f),
        ) { page ->
            var frame by remember { mutableStateOf<LayoutCoordinates?>(null) }
            MbProductImage(
                images.getOrNull(page),
                // No ripple: a wash of ink over a photograph reads as the
                // picture changing rather than as a tap landing. What answers
                // the tap is the full-screen view itself.
                modifier = Modifier
                    .fillMaxSize()
                    .onGloballyPositioned { frame = it }
                    .mbTap {
                        val coordinates = frame
                        if (coordinates != null && coordinates.isAttached) {
                            onOpen(
                                Rect(
                                    coordinates.positionInRoot(),
                                    coordinates.size.toSize(),
                                )
                            )
                        }
                    },
                // No scaling. The photograph fills its frame exactly, so
                // anything under full size pulls it off the edges and shows
                // the frame's ground down both sides — which is the seam this
                // page has spent long enough getting rid of.
                shape = RectangleShape,
                // The whole product, uncropped: the taller frame exists so the
                // photo can be seen in full, so a crop would defeat it.
                contentScale = ContentScale.Fit,
            )
        }

        if (images.size > 1) {
            Row(
                Modifier
                    .align(Alignment.BottomCenter)
                    .padding(bottom = 18.dp)
                    .graphicsLayer { alpha = 1f - closed() }
                    // On a pill of their own. They sit on the photograph now,
                    // and drawn in the theme's ink they went missing on every
                    // picture that happened to be the same tone.
                    .clip(CircleShape)
                    .background(MbTheme.colors.scrim)
                    .padding(horizontal = 9.dp, vertical = 7.dp),
                horizontalArrangement = Arrangement.spacedBy(5.dp),
            ) {
                repeat(images.size) { index ->
                    val active = index == pager.currentPage
                    val width by animateDpAsState(
                        if (active) 18.dp else 6.dp,
                        tween(240, easing = FastOutSlowInEasing),
                        label = "heroDot",
                    )
                    val color by animateColorAsState(
                        if (active) MbTheme.colors.onScrim
                        else MbTheme.colors.onScrim.copy(alpha = 0.45f),
                        tween(240),
                        label = "heroDotColor",
                    )
                    Box(Modifier.size(width, 6.dp).clip(CircleShape).background(color))
                }
            }
        }
      }
    }
}

/**
 * The bar over the photo: three buttons, and a surface that arrives under them.
 *
 * Nothing else. It used to collect the product's name and its price as the page
 * scrolled, which meant the top of the screen carried a second copy of both —
 * the panel below has them, the buy bar at the foot of the screen has the
 * number, and a third set sliding into a bar that already holds three controls
 * made the top of the page busiest exactly when the customer had scrolled past
 * the part that needed explaining. The buttons never move; all that changes is
 * the ground behind them.
 */
@Composable
fun ProductChrome(
    product: ProductDto?,
    /**
     * How far the page has covered the photograph behind this bar, 0..1.
     *
     * Driven by the panel below reaching the bar's own bottom edge, which is the
     * moment what is behind the bar stops being a photograph and starts being
     * the page.
     */
    cover: () -> Float,
    onBack: () -> Unit,
    onToggleFavorite: () -> Unit,
    onShare: () -> Unit,
) {
    val surface = MbTheme.colors.surface

    Column(
        Modifier
            .fillMaxWidth()
            // Crossfades from the hero's own ground to the page's surface,
            // rather than fading the surface up from nothing: half-opaque over
            // a photo is a grey band sliding down the picture, which is what
            // this looked like. Read in the draw phase, so following the
            // scroll invalidates drawing only.
            .drawBehind {
                // A wash first, then the page's surface over it.
                //
                // The photograph runs to the top of the screen, so what is
                // behind the system's own clock and battery is whatever the
                // seller photographed. The wash is what makes them readable on
                // any of it — strongest at the very edge and gone by the row of
                // buttons, so it reads as the picture darkening rather than as
                // a band laid across it. It belongs here, on the bar, which is
                // pinned to the top of the screen: put on the frame instead it
                // hung back with the picture and scrolled off, leaving the
                // clock bare on whatever was underneath.
                drawRect(
                    Brush.verticalGradient(
                        0f to Color.Black.copy(alpha = 0.55f),
                        0.55f to Color.Black.copy(alpha = 0.18f),
                        1f to Color.Transparent,
                    )
                )
                // Brought up steeply, and it covers the wash as it arrives.
                // Painted flat from the start it would band the picture, and
                // cross-fading two grounds never adds up to opaque in between —
                // at halfway a pair covers 0.75, and the wash showed through as
                // a grey band sliding down the picture. Full strength by an
                // eighth of the crossing, which is a few pixels of the page.
                drawRect(surface, alpha = barCover(cover()))
            }
            // The held inset, not the live one: see [statusBarTop]. Uneven top
            // and bottom on purpose, see [ChromeRowHeight] — the clock and the
            // battery are directly above these buttons and need the room.
            .padding(
                start = 14.dp,
                end = 14.dp,
                top = statusBarTop() + 18.dp,
                bottom = 10.dp,
            )
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            GlassButton("arrow-left", cover = cover, onClick = onBack)
            Spacer(Modifier.weight(1f))
            if (product != null) {
                GlassButton(
                    glyph = "heart",
                    filled = product.isFavorite,
                    tint = if (product.isFavorite) MbTheme.colors.danger else null,
                    cover = cover,
                    onClick = onToggleFavorite,
                )
                Spacer(Modifier.width(6.dp))
                GlassButton("share", cover = cover, onClick = onShare)
            }
        }
    }
}

/**
 * A circular button legible on a photograph and on a plain surface alike: the
 * bar's own fill, which is a step off both.
 *
 * Sized to be hit rather than to be tidy. At 36 dp these were under the 44 dp
 * a thumb needs, and they are the three controls sitting on a photograph where
 * a miss scrolls the page instead — so they are 46 dp, with the glyph grown to
 * match rather than left rattling around inside.
 */
@Composable
private fun GlassButton(
    glyph: String,
    modifier: Modifier = Modifier,
    filled: Boolean = false,
    tint: Color? = null,
    /**
     * How far the bar has grown its own surface, 0..1.
     *
     * The pill under the glyph is there to lift it off a photograph. Once the
     * bar is a white surface the pill has nothing left to do, and three grey
     * discs on a white bar are three more shapes than the row needs — so it
     * thins out as the surface arrives and the glyphs are left standing on the
     * bar, as they are on every other screen's header.
     */
    cover: () -> Float = { 0f },
    onClick: () -> Unit,
) {
    val ground = MbTheme.colors.fill
    Box(
        modifier
            .size(46.dp)
            .clip(CircleShape)
            // Read in the draw phase: following the scroll costs a repaint, not
            // a recomposition.
            .drawBehind { drawRect(ground, alpha = 1f - barCover(cover())) }
            // Rounded press, not the square flash a bare clickable draws: the
            // ripple is clipped to the circle by the clip above, and mbPressable
            // keeps the glyph unclipped inside it.
            .mbPressable(CircleShape, MbTheme.colors.ink.copy(alpha = 0.10f), onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        MbIcon(
            glyph,
            size = 23.dp,
            tint = tint ?: MbTheme.colors.ink,
            strokeWidth = 1.9f,
            filled = filled,
        )
    }
}

/**
 * The way to buy the thing: one line of facts, and one button.
 *
 * The price is not down here any more. It was on the left of the bar, in a
 * column of its own, on the grounds that a customer down among the reviews
 * should not have to scroll back up to see the number they are agreeing to —
 * but they never had to, because the top bar carries the price the moment the
 * panel holding it scrolls away ([MbHeroPrice] with `compact`). So the number
 * was on the screen twice, and the second copy was taking the width the button
 * wanted and pushing the delivery note into the button as a second line.
 *
 * That second line is what made the bar jump. A button with a subtitle is
 * 58 dp and a button without one is 48 dp, so the bar was 58 dp tall while the
 * product was not in the basket and 48 dp the instant it went in — the thing
 * under the thumb changed size as it was pressed, and the stepper that replaced
 * the price was 44 dp, which matched neither. Now the facts share one line
 * above, and the button is [MbDimens.buttonHeight] in both shapes with the
 * stepper standing at exactly that height beside it.
 *
 * Once the product is in the cart the button gives way to a quantity stepper, so
 * hammering the same spot adjusts a count instead of piling duplicate lines into
 * the cart.
 */
@Composable
fun BuyBar(
    product: ProductDto,
    /**
     * The shelf the bar is buying off: the chosen colour's share of it, not the
     * product's total. The photograph above is of one colour and the stepper
     * below is for one colour, so a ceiling taken from the sum of every colour
     * is a ceiling for something nobody is buying.
     */
    stockLeft: Int,
    inStock: Boolean,
    adding: Boolean,
    line: CartItemDto?,
    onAdd: () -> Unit,
    onSetQuantity: (itemId: Int, quantity: Int) -> Unit,
    onOpenCart: () -> Unit,
) {
    Column(
        Modifier
            .fillMaxWidth()
            .background(MbTheme.colors.surface)
            .windowInsetsPadding(WindowInsets.navigationBars)
            .padding(horizontal = 20.dp, vertical = 14.dp)
    ) {
        // One line of facts above the button: how many are left, and when it
        // arrives. Both used to be somewhere worse — the count was a clause in
        // the seller's row a third of the way down the page, and the delivery
        // note was the second line inside the button, which is what made the
        // button two heights. Here they are the same line whichever shape the
        // bar is in, so the button below them never moves.
        val note = product.deliveryNote.takeIf { it.isNotBlank() && inStock }
        if (stockLeft > 0 || note != null) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                StockLine(stockLeft)
                if (note != null) {
                    if (stockLeft > 0) {
                        MbText(" · ", MbTheme.type.micro, MbTheme.colors.textQuaternary)
                    }
                    MbText(
                        note,
                        MbTheme.type.micro,
                        MbTheme.colors.textQuaternary,
                        maxLines = 1,
                    )
                }
            }
            Spacer(Modifier.height(8.dp))
        }
        Row(verticalAlignment = Alignment.CenterVertically) {
            if (line == null) {
                // The whole bar, because there is nothing else on this line
                // now. One button at one height, which is the same height it
                // will be once the stepper appears beside it.
                MbPrimaryButton(
                    text = stringResource(
                        if (inStock) R.string.savatga else R.string.mavjud_emas
                    ),
                    onClick = onAdd,
                    enabled = inStock,
                    loading = adding,
                    modifier = Modifier.weight(1f),
                )
            } else {
                // In the cart already: the stepper takes the left, and the rest
                // of the bar becomes the way through to the cart. Leaving that
                // half empty gave a full-width bar one small control in the
                // corner and no way onward.
                MbQuantityStepper(
                    quantity = line.quantity,
                    onChange = { onSetQuantity(line.id, it) },
                    min = 0,
                    // Where the shelf ends. The bar could otherwise walk the
                    // count up to ninety-nine of something there were three of.
                    max = stockLeft.coerceAtLeast(1),
                    // The button's own height, not 44: the stepper stands
                    // beside it and the two have to read as one bar. Four dp
                    // apart is not a design, it is a mistake you can see.
                    size = MbTheme.dimens.buttonHeight,
                )
                Spacer(Modifier.width(12.dp))
                MbPrimaryButton(
                    text = stringResource(R.string.otish),
                    onClick = onOpenCart,
                    leadingGlyph = "cart",
                    modifier = Modifier.weight(1f),
                )
            }
        }
    }
}

/**
 * The rail at the foot of the page, with chips over it.
 *
 * Two readings of the same set rather than two requests: what the catalogue
 * considers similar, and the same list by how much people have reviewed it.
 * A genuine "recently viewed" needs a view history the app does not keep yet.
 */
@Composable
fun Recommendations(
    products: List<ProductCardDto>,
    onOpenProduct: (Int) -> Unit,
    modifier: Modifier = Modifier,
) {
    var tab by remember { mutableIntStateOf(0) }
    val ordered = remember(products, tab) {
        if (tab == 0) products else products.sortedByDescending { it.reviewsCount }
    }

    // On the page's grey ground rather than on a white panel.
    //
    // The panel was there to stop the section reading as a different screen
    // having started at the bottom of a long white page — but the things it was
    // drawn behind are white product cards, and a white card on a white panel
    // is a card nobody can see. It is the same trade the home page had, and it
    // goes the same way: the cards keep the grey to stand on, and the heading
    // over them says the section is still this page.
    Column(
        modifier
            .fillMaxWidth()
            .background(MbTheme.colors.canvas)
            .padding(top = 16.dp, bottom = 16.dp)
    ) {
        SectionHeader(
            stringResource(R.string.oxshash_tovarlar),
            modifier = Modifier.padding(horizontal = 16.dp),
        )
        Spacer(Modifier.height(10.dp))
        Row(
            Modifier.padding(horizontal = 16.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            MbChip(
                label = stringResource(R.string.oxshash),
                selected = tab == 0,
                onClick = { tab = 0 },
            )
            MbChip(
                label = stringResource(R.string.ommabop),
                selected = tab == 1,
                onClick = { tab = 1 },
            )
        }
        Spacer(Modifier.height(14.dp))
        LazyRow(
            // The same edge and the same gap the home page's rails keep, which
            // is what the card width is sized against.
            contentPadding = PaddingValues(horizontal = MbTheme.dimens.homeEdge),
            horizontalArrangement = Arrangement.spacedBy(MbTheme.dimens.cardGap),
        ) {
            items(ordered, key = { it.id }) { item ->
                MbRailTile(
                    title = item.title,
                    price = item.price,
                    oldPrice = item.oldPrice,
                    discountPercent = item.discountPercent,
                    imageUrl = item.imageUrl,
                    inStock = item.inStock,
                    stockLeft = item.stockLeft,
                    onClick = { onOpenProduct(item.id) },
                )
            }
        }
    }
}

/** The shape of the page before its payload lands. */
@Composable
fun ProductSkeleton() {
    Column(Modifier.fillMaxSize()) {
        MbSkeleton(Modifier.fillMaxWidth().height(heroHeight()), RectangleShape)
        Column(Modifier.padding(16.dp)) {
            MbSkeleton(Modifier.width(140.dp).height(28.dp), MbTheme.shapes.badge)
            Spacer(Modifier.height(12.dp))
            MbSkeleton(Modifier.fillMaxWidth().height(18.dp), MbTheme.shapes.badge)
            Spacer(Modifier.height(8.dp))
            MbSkeleton(Modifier.width(200.dp).height(14.dp), MbTheme.shapes.badge)
            Spacer(Modifier.height(22.dp))
            repeat(3) {
                MbSkeleton(Modifier.fillMaxWidth().height(13.dp), MbTheme.shapes.badge)
                Spacer(Modifier.height(9.dp))
            }
        }
    }
}

/**
 * Hands the product to the system share sheet.
 *
 * The chooser is the customer's — nothing leaves the phone until they pick a
 * destination themselves.
 */
fun share(context: Context, product: ProductDto) {
    val intent = Intent(Intent.ACTION_SEND).apply {
        type = "text/plain"
        putExtra(
            Intent.EXTRA_TEXT,
            "${product.title}\nminibozor://product/${product.id}",
        )
        putExtra(Intent.EXTRA_SUBJECT, product.title)
    }
    context.startActivity(Intent.createChooser(intent, null))
}
