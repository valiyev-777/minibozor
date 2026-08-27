package uz.minibozor.ui.product

import android.content.Context
import android.content.Intent
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.expandHorizontally
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.shrinkHorizontally
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
import androidx.compose.foundation.layout.wrapContentWidth
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.PagerState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.RectangleShape
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import uz.minibozor.R
import uz.minibozor.core.design.MbText
import uz.minibozor.core.design.MbTheme
import uz.minibozor.core.design.mbTap
import uz.minibozor.core.design.component.MbChip
import uz.minibozor.core.design.component.MbPriceRow
import uz.minibozor.core.design.component.MbPrimaryButton
import uz.minibozor.core.design.component.MbQuantityStepper
import uz.minibozor.core.design.component.MbProductImage
import uz.minibozor.core.design.component.MbRailTile
import uz.minibozor.core.design.component.MbSkeleton
import uz.minibozor.core.design.component.SectionHeader
import uz.minibozor.core.design.icon.MbIcon
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
fun heroHeight(): Dp = LocalConfiguration.current.screenWidthDp.dp + chromeHeight()

/** The bar: the status bar inset plus the row of buttons under it. */
@Composable
fun chromeHeight(): Dp =
    WindowInsets.statusBars.asPaddingValues().calculateTopPadding() + 56.dp

/** Enough to sit behind the status bar and the row of buttons under it. */
private val StatusScrimHeight = 108.dp

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
) {
    Box(
        Modifier
            .fillMaxWidth()
            .height(heroHeight())
            // The theme's photo ground, the same one the grid tiles use.
            .background(MbTheme.colors.photoStudio)
    ) {
        // Below the bar, not under it: the frame is a square of photo plus the
        // bar's own height, so the whole picture is in the clear.
        HorizontalPager(
            pager,
            Modifier
                .fillMaxSize()
                .padding(top = chromeHeight()),
        ) { page ->
            MbProductImage(
                images.getOrNull(page),
                modifier = Modifier
                    .fillMaxSize()
                    .graphicsLayer {
                        // Both the swipe offset and the scroll are read here,
                        // in the layer phase. Reading the pager during
                        // composition instead recomposed every page on every
                        // frame of a swipe, which is what made it stutter.
                        val distance = ((pager.currentPage - page) +
                            pager.currentPageOffsetFraction).coerceIn(-1f, 1f)
                        val progress = closed()
                        translationY = progress * size.height * 0.30f
                        alpha = 1f - progress
                        val settled = 1f - kotlin.math.abs(distance)
                        val scale = (0.92f + 0.08f * settled) * (1f - 0.06f * progress)
                        scaleX = scale
                        scaleY = scale
                    },
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
                    .graphicsLayer { alpha = 1f - closed() },
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
                        if (active) MbTheme.colors.ink else MbTheme.colors.hairlineStrong,
                        tween(240),
                        label = "heroDotColor",
                    )
                    Box(Modifier.size(width, 6.dp).clip(CircleShape).background(color))
                }
            }
        }
    }
}

/**
 * The bar over the photo.
 *
 * The buttons never move: they sit on the photo to begin with and stay in
 * exactly the same place once the bar has a surface behind it. What changes is
 * underneath them — the name and price slide down into the row the photo has
 * vacated, so nothing about the product is ever off screen.
 */
@Composable
fun ProductChrome(
    product: ProductDto?,
    closed: () -> Float,
    /** How far the product's name has been handed from the page to this bar. */
    handover: () -> Float,
    onBack: () -> Unit,
    onToggleFavorite: () -> Unit,
    onShare: () -> Unit,
) {
    val surface = MbTheme.colors.surface
    val onPhoto = MbTheme.colors.photoStudio

    Column(
        Modifier
            .fillMaxWidth()
            // Crossfades from the hero's own ground to the page's surface,
            // rather than fading the surface up from nothing: half-opaque over
            // a photo is a grey band sliding down the picture, which is what
            // this looked like. Read in the draw phase, so following the
            // scroll invalidates drawing only.
            .drawBehind {
                // An opaque ground, then the page's surface faded over it.
                // Cross-fading two translucent rects never adds up to opaque
                // in between — at halfway the pair covers 0.75, so a quarter
                // of the card behind showed through, which is how the
                // product's name kept appearing twice.
                //
                // The ground itself comes up steeply rather than being there
                // from the start: painted flat over an untouched photo it put
                // a band across the picture, since a blurred backdrop has no
                // one colour to match. Full strength by an eighth of the
                // handover, which is a few pixels of the name — long before
                // any of it could read through.
                val h = handover()
                drawRect(onPhoto, alpha = (h * 8f).coerceAtMost(1f))
                drawRect(surface, alpha = h)
            }
            .windowInsetsPadding(WindowInsets.statusBars)
            .padding(horizontal = 14.dp, vertical = 10.dp)
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            GlassButton("arrow-left", closed, onClick = onBack)
            Spacer(Modifier.weight(1f))
            if (product != null) {
                GlassButton(
                    glyph = "heart",
                    closed = closed,
                    filled = product.isFavorite,
                    tint = if (product.isFavorite) MbTheme.colors.danger else null,
                    onClick = onToggleFavorite,
                )
                Spacer(Modifier.width(10.dp))
                GlassButton("share", closed, onClick = onShare)
            }
        }

        if (product != null) {
            // Held at a fixed height and faded, so the row below never jumps
            // as the text arrives.
            Row(
                Modifier
                    .fillMaxWidth()
                    .graphicsLayer {
                        val progress = handover()
                        alpha = progress
                        translationY = (progress - 1f) * 14.dp.toPx()
                    }
                    .padding(top = 10.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                // The price is measured first, at whatever width its digits
                // need, and the name takes what is left and ellipsises. That
                // ordering is the guarantee, not the spacing: a name of any
                // length cannot squeeze the price, and a price of any size
                // cannot reach the name — the gap between them is fixed.
                MbText(
                    product.title,
                    MbTheme.type.title1,
                    maxLines = 1,
                    modifier = Modifier.weight(1f),
                )
                Spacer(Modifier.width(14.dp))
                MbPriceRow(
                    product.price,
                    priceStyle = MbTheme.type.title2,
                    modifier = Modifier.wrapContentWidth(),
                )
            }
        }
    }
}

/**
 * A circular button legible on a photo and on a plain surface alike: it starts
 * as a light scrim over the picture and dissolves into the bar's own fill.
 */
@Composable
private fun GlassButton(
    glyph: String,
    closed: () -> Float,
    modifier: Modifier = Modifier,
    filled: Boolean = false,
    tint: Color? = null,
    onClick: () -> Unit,
) {
    val ground = MbTheme.colors.fill
    Box(
        modifier
            .size(36.dp)
            .clip(CircleShape)
            // One opaque fill. It used to cross-fade between two copies of this
            // same colour, which left it translucent halfway through for no
            // reason at all.
            .background(ground)
            .mbTap(onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        MbIcon(
            glyph,
            size = 18.dp,
            tint = tint ?: MbTheme.colors.ink,
            strokeWidth = 1.9f,
            filled = filled,
        )
    }
}

/**
 * Price on the left, the call to action on the right. Once the product is in
 * the cart the button gives way to a quantity stepper, so hammering the same
 * spot adjusts a count instead of piling duplicate lines into the cart.
 */
@Composable
fun BuyBar(
    product: ProductDto,
    adding: Boolean,
    line: CartItemDto?,
    showPrice: Boolean,
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
        Row(verticalAlignment = Alignment.CenterVertically) {
            // Once the page has scrolled the header shows the price, and two
            // prices at once read as a mistake — this one bows out and the
            // button stretches into the room it leaves.
            AnimatedVisibility(
                // Also stands down once the line exists: the stepper takes
                // this side of the bar then.
                visible = showPrice && line == null,
                enter = expandHorizontally() + fadeIn(),
                exit = shrinkHorizontally() + fadeOut(),
            ) {
                Row {
                    MbPriceRow(
                        product.price,
                        product.oldPrice,
                        product.discountPercent,
                        // The bar is where the decision gets made, so the
                        // number carries more weight here than in a tile.
                        priceStyle = MbTheme.type.title3,
                    )
                    Spacer(Modifier.width(14.dp))
                }
            }
            if (line == null) {
                MbPrimaryButton(
                    text = stringResource(
                        if (product.inStock) R.string.savatga else R.string.mavjud_emas
                    ),
                    onClick = onAdd,
                    enabled = product.inStock,
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
                    size = 44.dp,
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
fun Recommendations(products: List<ProductCardDto>, onOpenProduct: (Int) -> Unit) {
    var tab by remember { mutableIntStateOf(0) }
    val ordered = remember(products, tab) {
        if (tab == 0) products else products.sortedByDescending { it.reviewsCount }
    }

    Column(Modifier.fillMaxWidth().padding(top = 6.dp)) {
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
            contentPadding = PaddingValues(horizontal = 16.dp),
            horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            items(ordered, key = { it.id }) { item ->
                MbRailTile(
                    title = item.title,
                    price = item.price,
                    discountPercent = item.discountPercent,
                    imageUrl = item.imageUrl,
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
