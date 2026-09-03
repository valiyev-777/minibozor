package uz.minibozor.ui.product

import android.app.Activity
import androidx.activity.compose.BackHandler
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.graphics.RectangleShape
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.compose.ui.zIndex
import androidx.core.view.WindowCompat
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.LifecycleResumeEffect
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import uz.minibozor.R
import uz.minibozor.core.design.MbMotion
import uz.minibozor.core.design.MbText
import uz.minibozor.core.design.MbTheme
import uz.minibozor.core.design.component.MbCard
import uz.minibozor.core.design.component.MbDivider
import uz.minibozor.core.design.component.MbErrorState
import uz.minibozor.core.design.component.MbExpandableSection
import uz.minibozor.core.design.component.MbHeroPrice
import uz.minibozor.core.design.component.MbKeyValueRow
import uz.minibozor.core.design.component.MbReveal
import uz.minibozor.core.design.component.MbRichText
import uz.minibozor.core.design.component.SectionHeader
import uz.minibozor.core.design.component.rememberMbRevealState
import uz.minibozor.core.design.icon.MbIcon
import uz.minibozor.ui.common.MbToastHost
import uz.minibozor.ui.common.rememberToast
import uz.minibozor.ui.product.component.ColorPicker
import uz.minibozor.ui.product.component.RatingPanel
import uz.minibozor.ui.product.component.ReviewRow
import uz.minibozor.ui.product.component.SizePicker
import uz.minibozor.ui.product.component.ShelfLine

/**
 * The share of the scroll the photograph sits out.
 *
 * At 0.7 it climbs at three tenths of the page's pace, so seven tenths of what
 * you scroll is the panel below travelling up over it. The picture barely
 * leaves; it is covered where it stands.
 *
 * Held flat rather than tapered off. It used to ease back to nothing so the
 * photograph would leave with its own bounds — but the panel now meets it with
 * no gap between them, so by the time the list stops drawing the frame the
 * panel has already covered the last of it, and there is nothing left to see
 * go.
 */
private const val HeroLag = 0.7f

/** The seam between two sections, carried by the lower of the pair. */
private val SectionGap = Modifier.padding(top = 12.dp)

/**
 * The running order the page is read in, and the order it assembles in.
 *
 * The blocks enter staggered against these numbers and leave against them
 * reversed, so the page builds from the photograph down and comes apart from the
 * bottom up. Named rather than counted at the call sites: an `item` that is only
 * emitted for some products (the options, the description) would otherwise shift
 * every number under it, and the stagger would change with the product.
 */
private const val BlockHero = 0
private const val BlockIdentity = 1
private const val BlockOptions = 2
private const val BlockDescription = 3
private const val BlockSmallPrint = 4
private const val BlockReviews = 5
private const val BlockSimilar = 6

/** Screen 14 — Mahsulot. */
@Composable
fun ProductScreen(
    productId: Int,
    onBack: () -> Unit,
    onOpenReviews: (Int) -> Unit,
    onOpenProduct: (Int) -> Unit,
    onOpenCart: () -> Unit,
    viewModel: ProductViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val cartLine by viewModel.cartLine.collectAsStateWithLifecycle()
    val toast = rememberToast()
    LaunchedEffect(productId) { viewModel.load(productId) }

    // Every motion on this screen answers the scroll; nothing plays on its own,
    // apart from the page's own arrival and departure.
    val product = state.product
    val listState = rememberLazyListState()

    /** The page the full-screen view is showing, or null while it is closed. */
    var viewerPage by remember { mutableStateOf<Int?>(null) }

    /** Where on screen the picture it grew out of was sitting. */
    var viewerOrigin by remember { mutableStateOf<Rect?>(null) }

    // The page's own entrance and exit. The blocks read it; the back button
    // sets it and waits for them before the navigation actually happens, so the
    // page is seen leaving rather than being cut off mid-frame.
    val reveal = rememberMbRevealState()
    val scope = rememberCoroutineScope()
    fun leave() {
        if (reveal.leaving) return
        reveal.leave()
        scope.launch {
            delay(MbMotion.PageExit.toLong())
            onBack()
        }
    }

    // Only while the photograph is not the screen: the full-screen view has a
    // back handler of its own, and it takes the gesture first.
    BackHandler(enabled = viewerPage == null) { leave() }

    val density = LocalDensity.current
    val statusBarPx = WindowInsets.statusBars.getTop(density).toFloat()
    val heroHeight = heroHeight()
    val heroHeightPx = with(density) { heroHeight.toPx() }
    val closePx = heroHeightPx * 0.55f

    /** 0 while the photo fills the top, 1 once it has closed away behind. */
    val closed by remember {
        derivedStateOf {
            if (listState.firstVisibleItemIndex > 0) {
                1f
            } else {
                (listState.firstVisibleItemScrollOffset / closePx).coerceIn(0f, 1f)
            }
        }
    }

    // Where the bar's own bottom edge sits, and how far the page travels past it
    // before the bar's surface is fully its own.
    val barBottomPx = statusBarPx + with(density) { ChromeRowHeight.toPx() }
    val crossingPx = with(density) { 20.dp.toPx() }

    /**
     * How far the page has covered the photograph behind the bar, 0..1.
     *
     * The panel below the photograph is drawn over it, so the moment its top
     * edge passes the bar's bottom edge is the moment what is behind the bar
     * stops being a photograph. That is when the bar grows its own surface, and
     * when the system's clock and battery are handed back to the theme — one
     * number for both, so they can never disagree.
     */
    val cover by remember {
        derivedStateOf {
            val identity = listState.layoutInfo.visibleItemsInfo
                .firstOrNull { it.key == "identity" }
            if (identity == null) {
                if (listState.firstVisibleItemIndex > 0) 1f else 0f
            } else {
                ((barBottomPx - identity.offset) / crossingPx).coerceIn(0f, 1f)
            }
        }
    }

    // The photograph runs to the top of the screen, so the system's own clock
    // and battery are drawn on it. They are held light for as long as that is
    // true — the wash under them is dark whatever the picture — and handed
    // back to the theme the moment that stops being true.
    val view = LocalView.current
    val darkTheme = MbTheme.colors.isDark
    // Light exactly while the wash is what is behind them: the bar's surface
    // covers that wash the moment barCover reaches 1, and the icons change with
    // it rather than at some threshold of their own. Light over the full-screen
    // photograph too, whose ground is black in either theme.
    val overPhoto by remember { derivedStateOf { barCover(cover) < 1f } }
    val lightBars = overPhoto || viewerPage != null

    /**
     * The window's bar icons, set only while this page is the resumed one.
     *
     * This is the fix for a clock that went missing all over the app. The window
     * is one object and every screen shares it, so a screen that forces white
     * icons has to put them back — and a plain `SideEffect` plus `onDispose`
     * could not say when. Pushing one product from another composed the new page
     * (white icons, it opens on a photograph) before the old one was disposed,
     * and the old page's tidy-up then set them dark again over the new page's
     * photograph; the reverse left white icons on a white screen. Either way the
     * clock and the battery were invisible until something happened to
     * recompose.
     *
     * Tied to the resumed state instead, the order is the navigator's and it is
     * always the same: the page being left pauses and puts the icons back, then
     * the page arriving resumes and asks for what it needs.
     */
    LifecycleResumeEffect(lightBars, darkTheme) {
        val window = (view.context as? Activity)?.window
        fun light(value: Boolean) {
            if (window != null) {
                WindowCompat.getInsetsController(window, view)
                    .isAppearanceLightStatusBars = value
            }
        }
        light(if (lightBars) false else !darkTheme)
        onPauseOrDispose { light(!darkTheme) }
    }

    val heroPager = rememberPagerState(
        pageCount = { maxOf(product?.images?.size ?: 1, 1) },
    )

    val context = LocalContext.current

    // The photograph and the colour are one choice made two ways. A colour is
    // a photograph of the product in it, and most of those photographs are also
    // pages of the hero — so swiping to the black one is choosing black, and
    // tapping the black swatch turns the page to it. Whichever way the choice is
    // made the page agrees with itself, and the count under the picture is the
    // count of what is in the picture.
    val productColors = remember(product) {
        product?.variants.orEmpty().filter { it.kind == "color" }
    }
    val pageOfColor = remember(product) {
        productColors.mapNotNull { color ->
            val page = product?.images.orEmpty()
                .indexOf(color.imageUrl ?: return@mapNotNull null)
            if (page < 0) null else color.id to page
        }.toMap()
    }
    LaunchedEffect(heroPager.currentPage, pageOfColor) {
        val id = pageOfColor.entries.firstOrNull { it.value == heroPager.currentPage }?.key
        if (id != null && id != state.selectedColorId) viewModel.selectColor(id)
    }
    LaunchedEffect(state.selectedColorId, pageOfColor) {
        val page = pageOfColor[state.selectedColorId]
        if (page != null && page != heroPager.currentPage) heroPager.animateScrollToPage(page)
    }

    // What the page is actually about: the colour on show, or the product
    // itself when it has no colours to speak of. A colour the shop does not
    // count apart falls back to the whole shelf.
    val selectedColor = productColors.firstOrNull { it.id == state.selectedColorId }
        ?: productColors.firstOrNull()
    val shelfLeft = selectedColor?.stockLeft ?: product?.stockLeft ?: 0
    val shelfInStock = product?.inStock == true && (selectedColor?.inStock ?: true)

    // And what can actually be bought, which is a narrower question than what
    // is on the shelf. The line under the rating answers about the colour in
    // the photograph above it; the bar at the bottom is buying one colour in
    // one size, so its ceiling is whichever of the two is scarcer. Seventeen in
    // blue and one in a 45 is one pair to sell, and a stepper offering
    // seventeen of them is an offer the server refuses.
    val selectedSize = product?.variants.orEmpty()
        .firstOrNull { it.kind == "size" && it.id == state.selectedSizeId }
    val buyableLeft = listOfNotNull(
        selectedColor?.stockLeft,
        selectedSize?.stockLeft,
    ).minOrNull() ?: shelfLeft
    val buyable = shelfInStock && (selectedSize?.inStock ?: true)

    Box(
        Modifier
            .fillMaxSize()
            .background(MbTheme.colors.canvas)
    ) {
            when {
                state.loading -> ProductSkeleton()
                state.error != null -> MbErrorState(
                    state.error!!,
                    viewModel::retry,
                    Modifier.windowInsetsPadding(WindowInsets.statusBars),
                )
                else -> product?.let { product ->
                    val sizes = product.variants.filter { it.kind == "size" }
                    val colors = product.variants.filter { it.kind == "color" }
                    val hasOptions = sizes.isNotEmpty() || colors.isNotEmpty()

                    LazyColumn(
                        Modifier.fillMaxSize(),
                        state = listState,
                        // Room at the bottom for the buy bar to float over.
                        contentPadding = PaddingValues(bottom = 120.dp),
                        // No blanket spacing: the first panel has to butt
                        // straight up against the photograph, or the gap is
                        // still uncovered at the moment the list stops drawing
                        // the photograph and shows as a strip of bare page.
                        // Every panel after it carries its own gap instead.
                    ) {
                        // The photo runs edge to edge under the status bar and
                        // closes away behind the content as you scroll past it.
                        item(key = "hero") {
                            // Fades only: it runs under the status bar, and a
                            // photograph rising into place there leaves a strip
                            // of bare page above it the whole way up.
                            MbReveal(reveal, "hero", BlockHero, rise = 0.dp) {
                                Hero(
                                    images = product.images,
                                    closed = { closed },
                                    pager = heroPager,
                                    // Read here, in the lambda, so the scroll is
                                    // followed in the layer phase rather than
                                    // recomposing this item on every frame.
                                    lag = {
                                        if (listState.firstVisibleItemIndex > 0) 0f
                                        else listState.firstVisibleItemScrollOffset * HeroLag
                                    },
                                    onOpen = { bounds ->
                                        viewerOrigin = bounds
                                        viewerPage = heroPager.currentPage
                                    },
                                )
                            }
                        }

                        // The order the page is read in: what it is and what it
                        // costs, what buyers made of it, which one to buy, the
                        // seller's own description, the small print, and the
                        // reviews in full. Grouped by what a section is for
                        // rather than one card per fact.
                        item(key = "identity") {
                            // Above the photo, and it overlaps it because the
                            // photo hangs back — so the panel is seen crossing
                            // in front of the picture rather than arriving once
                            // the picture has gone. The zIndex belongs on the
                            // item's own root, which is the reveal.
                            MbReveal(
                                reveal,
                                "identity",
                                BlockIdentity,
                                modifier = Modifier.zIndex(1f),
                            ) {
                                MbCard(shape = RectangleShape) {
                                    // Name first, then the number.
                                    //
                                    // The name is what the page is about and the
                                    // price is the fact being weighed about it,
                                    // so the name leads at the panel's heaviest
                                    // size and the price answers it a step
                                    // below, set larger still but on its own
                                    // line with the saving beside it. Read in
                                    // that order it is a sentence; the other way
                                    // round it was a number looking for a
                                    // subject.
                                    //
                                    // The page's only copy of the name: the bar
                                    // above carries nothing but its three
                                    // buttons.
                                    MbText(product.title, MbTheme.type.title1)
                                    if (product.subtitle.isNotBlank()) {
                                        Spacer(Modifier.height(5.dp))
                                        MbText(
                                            product.subtitle,
                                            MbTheme.type.bodySmall,
                                            MbTheme.colors.textTertiary,
                                        )
                                    }
                                    Spacer(Modifier.height(12.dp))
                                    MbHeroPrice(
                                        price = product.price,
                                        oldPrice = product.oldPrice,
                                        discountPercent = product.discountPercent,
                                    )
                                    // Where the description used to be. What a
                                    // stranger's page owes a buyer at this point
                                    // is other buyers, not the seller's own
                                    // prose.
                                    Spacer(Modifier.height(16.dp))
                                    RatingPanel(
                                        rating = state.summary?.rating ?: product.rating,
                                        reviewsCount = state.summary?.total
                                            ?: product.reviewsCount,
                                        photos = state.summary?.photos.orEmpty(),
                                        photosTotal = state.summary?.photosTotal ?: 0,
                                        onClick = { onOpenReviews(product.id) },
                                    )
                                    // What is on the shelf, right under what
                                    // other people made of it: the evidence
                                    // someone weighs between the price above and
                                    // the choice below. One line, because that
                                    // is all it has to say.
                                    Spacer(Modifier.height(10.dp))
                                    ShelfLine(
                                        stockLeft = shelfLeft,
                                        soldCount = product.soldCount,
                                        inStock = shelfInStock,
                                    )
                                }
                            }
                        }

                        if (hasOptions) {
                            item(key = "options") {
                                MbReveal(reveal, "options", BlockOptions, modifier = SectionGap) {
                                    MbCard(shape = RectangleShape) {
                                        // Colour first, then size: the colour is
                                        // what the photograph above is showing,
                                        // and changing it changes what a size is
                                        // being chosen for.
                                        if (colors.isNotEmpty()) {
                                            ColorPicker(
                                                colors = colors,
                                                selectedId = state.selectedColorId,
                                                onSelect = viewModel::selectColor,
                                                productImages = product.images,
                                            )
                                        }
                                        if (sizes.isNotEmpty() && colors.isNotEmpty()) {
                                            Spacer(Modifier.height(16.dp))
                                            MbDivider()
                                            Spacer(Modifier.height(16.dp))
                                        }
                                        if (sizes.isNotEmpty()) {
                                            SizePicker(
                                                sizes = sizes,
                                                selectedId = state.selectedSizeId,
                                                onSelect = viewModel::selectSize,
                                            )
                                        }
                                    }
                                }
                            }
                        }

                        // Straight after the choice, and above the small print.
                        //
                        // A description is what someone reads once they have
                        // decided to care — a page of prose and photographs
                        // between the name and the "which one" is a page nobody
                        // scrolls past, and buried under the specifications it
                        // is a page nobody finds. It renders headings, lists and
                        // the shop's own photographs, folded down to its opening
                        // lines with the rest behind "Batafsil", so a seller can
                        // write a page rather than a paragraph without the page
                        // costing every customer a page of scrolling.
                        if (product.description.isNotBlank()) {
                            item(key = "description") {
                                MbReveal(
                                    reveal,
                                    "description",
                                    BlockDescription,
                                    modifier = SectionGap,
                                ) {
                                    MbCard(shape = RectangleShape) {
                                        SectionHeader(stringResource(R.string.tavsif))
                                        Spacer(Modifier.height(12.dp))
                                        MbRichText(product.description)
                                    }
                                }
                            }
                        }

                        // The small print, folded: the numbers first, then the
                        // terms.
                        item(key = "smallprint") {
                            MbReveal(
                                reveal,
                                "smallprint",
                                BlockSmallPrint,
                                modifier = SectionGap,
                            ) {
                                MbCard(shape = RectangleShape) {
                                    if (product.specs.isNotEmpty()) {
                                        MbExpandableSection(
                                            title = stringResource(R.string.xususiyatlari),
                                            subtitle = pluralStringResource(
                                                R.plurals.n_items,
                                                product.specs.size,
                                                product.specs.size,
                                            ),
                                        ) {
                                            Column {
                                                product.specs.forEach {
                                                    MbKeyValueRow(it.key, it.value)
                                                }
                                            }
                                        }
                                        Spacer(Modifier.height(14.dp))
                                        MbDivider()
                                        Spacer(Modifier.height(14.dp))
                                    }
                                    // Folded, but the delivery line rides on the
                                    // header: it is the one fact here that helps
                                    // someone decide, and hiding it to tidy the
                                    // page would be a poor trade.
                                    MbExpandableSection(
                                        title = stringResource(R.string.yetkazish_va_kafolat),
                                        subtitle = product.deliveryNote,
                                    ) {
                                        Column {
                                            DeliveryRow(
                                                "box",
                                                stringResource(R.string.yetkazish),
                                                product.deliveryNote,
                                            )
                                            MbDivider()
                                            DeliveryRow(
                                                "ret",
                                                stringResource(R.string.qaytarish),
                                                stringResource(
                                                    R.string.qaytarish_14_kun_ichida_qadoq_butun_bolsa
                                                ),
                                            )
                                            if (product.warranty != null) {
                                                MbDivider()
                                                DeliveryRow(
                                                    "gear",
                                                    stringResource(R.string.kafolat),
                                                    product.warranty,
                                                )
                                            }
                                            MbDivider()
                                            DeliveryRow(
                                                "basket",
                                                stringResource(R.string.sotuvchi),
                                                // The seller, and only the
                                                // seller. What is left moved to
                                                // the buy bar, where the count
                                                // is a reason rather than a
                                                // clause in a row about
                                                // delivery.
                                                product.seller,
                                            )
                                        }
                                    }
                                }
                            }
                        }

                        item(key = "reviews") {
                            MbReveal(reveal, "reviews", BlockReviews, modifier = SectionGap) {
                                MbCard(shape = RectangleShape) {
                                    SectionHeader(
                                        title = stringResource(R.string.sharhlar),
                                        subtitle = state.summary?.let {
                                            pluralStringResource(
                                                R.plurals.n_items,
                                                it.total,
                                                it.total,
                                            )
                                        },
                                        actionLabel = stringResource(R.string.barchasi),
                                        onAction = { onOpenReviews(product.id) },
                                    )
                                    Spacer(Modifier.height(12.dp))
                                    state.topReviews.forEach { review ->
                                        ReviewRow(review, onLike = null)
                                        Spacer(Modifier.height(12.dp))
                                    }
                                    if (state.topReviews.isEmpty()) {
                                        MbText(
                                            stringResource(R.string.hali_sharh_yoq_birinchi_boling),
                                            MbTheme.type.bodySmall,
                                            MbTheme.colors.icon,
                                        )
                                    }
                                }
                            }
                        }

                        if (state.similar.isNotEmpty()) {
                            item(key = RecommendationsKey) {
                                MbReveal(
                                    reveal,
                                    RecommendationsKey,
                                    BlockSimilar,
                                    modifier = SectionGap,
                                ) {
                                    Recommendations(
                                        products = state.similar,
                                        onOpenProduct = onOpenProduct,
                                    )
                                }
                            }
                        }
                    }
                }
            }
            // Over the photo: three circular buttons that stay put while the
            // bar grows a surface under them, then the name and price arrive.
            // It leaves with the page rather than sitting on a page that is
            // already going.
            val chromeAlpha by animateFloatAsState(
                targetValue = if (reveal.leaving) 0f else 1f,
                animationSpec = tween(MbMotion.Quick, easing = MbMotion.EaseIn),
                label = "chromeExit",
            )
            Box(Modifier.graphicsLayer { alpha = chromeAlpha }) {
                ProductChrome(
                    product = product,
                    cover = { cover },
                    onBack = { leave() },
                    onToggleFavorite = viewModel::toggleFavorite,
                    onShare = { product?.let { share(context, it) } },
                )
            }

            // Always there. The way to buy the thing never leaves the screen —
            // it carries the price and the button together — and it slides out
            // the way it came in as the page leaves.
            AnimatedVisibility(
                visible = product != null && !reveal.leaving,
                enter = slideInVertically(
                    tween(MbMotion.Emphasized, easing = MbMotion.EaseOut),
                ) { it } + fadeIn(tween(MbMotion.Standard, easing = MbMotion.EaseOut)),
                exit = slideOutVertically(
                    tween(MbMotion.Quick, easing = MbMotion.EaseIn),
                ) { it } + fadeOut(tween(MbMotion.Quick, easing = MbMotion.EaseIn)),
                modifier = Modifier.align(Alignment.BottomCenter),
            ) {
                product?.let {
                    BuyBar(
                        product = it,
                        stockLeft = buyableLeft,
                        inStock = buyable,
                        adding = state.adding,
                        line = cartLine,
                        onAdd = { viewModel.addToCart { message -> toast.value = message } },
                        onSetQuantity = viewModel::setCartQuantity,
                        onOpenCart = onOpenCart,
                    )
                }
            }

            MbToastHost(toast, Modifier.align(Alignment.BottomCenter).padding(bottom = 96.dp))

            // Over everything, including the bar and the buy bar: while it is
            // open the photograph is the screen. It grows out of the picture
            // that was tapped and goes back into it.
            viewerPage?.let { page ->
                HeroViewer(
                    images = product?.images.orEmpty(),
                    initialPage = page,
                    origin = viewerOrigin,
                    onClose = { viewerPage = null },
                )
            }
        }
}

@Composable
private fun DeliveryRow(glyph: String, title: String, subtitle: String) {
    Row(
        Modifier
            .fillMaxWidth()
            .padding(vertical = 12.dp),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        MbIcon(glyph, size = 18.dp, tint = MbTheme.colors.accent)
        Column(Modifier.weight(1f)) {
            MbText(
                title,
                MbTheme.type.body.copy(
                    fontWeight = androidx.compose.ui.text.font.FontWeight.Bold),
            )
            MbText(subtitle, MbTheme.type.meta, MbTheme.colors.icon)
        }
    }
}
