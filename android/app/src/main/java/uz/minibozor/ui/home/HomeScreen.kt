package uz.minibozor.ui.home

import uz.minibozor.core.util.mediaUrl
import coil.compose.AsyncImage
import kotlinx.coroutines.delay
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.animation.core.tween
import androidx.compose.ui.geometry.Size
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.animateDpAsState
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.animateColorAsState
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.runtime.derivedStateOf
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.draw.drawBehind
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.PagerState
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.Composable
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import uz.minibozor.R
import uz.minibozor.core.design.component.MbDivider
import uz.minibozor.core.design.component.MbRadioRow
import uz.minibozor.core.design.mbClickable
import uz.minibozor.core.util.UZ_REGIONS
import uz.minibozor.core.util.regionLabel
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.CompositingStrategy
import androidx.compose.ui.graphics.RectangleShape
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import uz.minibozor.core.design.MbText
import uz.minibozor.core.design.MbPressAlpha
import uz.minibozor.core.design.mbPressable
import uz.minibozor.core.design.MbTheme
import uz.minibozor.core.design.component.MbCard
import uz.minibozor.core.design.component.MbDealTile
import uz.minibozor.core.design.component.MbProductImage
import uz.minibozor.core.design.component.MbProductTile
import uz.minibozor.core.design.component.MbRailTile
import uz.minibozor.core.design.component.MbScreen
import uz.minibozor.core.design.component.MbSearchPill
import uz.minibozor.core.design.component.MbTabBarSpacer
import uz.minibozor.core.design.component.SectionHeader
import uz.minibozor.core.design.icon.MbIcon
import uz.minibozor.core.util.toColor
import uz.minibozor.data.remote.dto.BannerDto
import uz.minibozor.data.remote.dto.CategoryDto
import uz.minibozor.data.remote.dto.ProductCardDto
import uz.minibozor.data.remote.dto.SectionDto
import uz.minibozor.ui.product.VariantSheet
import uz.minibozor.ui.common.MbToastHost
import uz.minibozor.ui.common.UiStateContent
import uz.minibozor.ui.common.rememberToast

/**
 * The 20 dp card corners, split across a card's lazy fragments. A section card
 * is emitted as several small lazy items (header, rows, rail) rather than one
 * card-sized item — composing a whole card in a single frame is what made the
 * scroll hitch — so the top and bottom fragments each carry their half of the
 * card's rounding and the middle fragments draw a plain surface.
 */
/** How many times the banners are repeated so the carousel can run on. */
private const val BannerLoops = 1000

/** What a rail spends before its first tile, and after its last. */
private val RailEdge = 20.dp

private val CardTopShape = RoundedCornerShape(topStart = 20.dp, topEnd = 20.dp)
private val CardBottomShape = RoundedCornerShape(bottomStart = 20.dp, bottomEnd = 20.dp)

/** The gap between blocks; explicit because spacedBy would split card fragments. */
private val SectionGap = 12.dp

/**
 * Screen 07. One request fills the whole page: banners, the 5x2 category grid,
 * a deals pair, a two-column recommendation grid and two horizontal rails.
 */
@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
fun HomeScreen(
    onOpenSearch: () -> Unit,
    onOpenCategory: (CategoryDto) -> Unit,
    onOpenBanner: (BannerDto) -> Unit,
    onOpenProduct: (Int) -> Unit,
    onOpenListing: (category: String?, title: String) -> Unit,
    onOpenCart: () -> Unit,
    viewModel: HomeViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val city by viewModel.city.collectAsStateWithLifecycle()
    val toast = rememberToast()
    var showRegions by remember { mutableStateOf(false) }
    // A product that comes in sizes or colours opens the picker instead of
    // being added with a variant we guessed for the customer.
    var picking by remember { mutableStateOf<ProductCardDto?>(null) }
    var refreshing by remember { mutableStateOf(false) }

    MbScreen { padding ->
        Box(Modifier.fillMaxSize()) {
            UiStateContent(
                state = state,
                onRetry = viewModel::load,
                modifier = Modifier.padding(padding),
                loading = { HomeSkeleton(it) },
            ) { home ->
                // Hoisted out of the lazy item that draws it. A pager built
                // inside the list is torn down the moment the banners scroll
                // off the top and stood back up — new pager, new page, new
                // timer — when they come back, which is both a hitch in that
                // frame and a lost place in the carousel.
                // Far more pages than anyone will swipe, and started in the
                // middle of them, so the carousel only ever moves forward.
                // Counting the real banners meant the step after the last one
                // was a scroll back to zero — three animating backwards past
                // two to reach one, which is the carousel unwinding itself
                // rather than coming round.
                val feed = rememberLazyListState()
                // True once the city row above the search has gone: the row is
                // the list's first item, so anything else at the top means the
                // search is standing on its own over the feed.
                val stuck by remember { derivedStateOf { feed.firstVisibleItemIndex > 0 } }
                val bannerPager = rememberPagerState(
                    initialPage = if (home.banners.isEmpty()) 0 else BannerLoops / 2 * home.banners.size,
                    pageCount = { if (home.banners.isEmpty()) 0 else home.banners.size * BannerLoops },
                )

                PullToRefreshBox(
                    isRefreshing = refreshing,
                    onRefresh = {
                        refreshing = true
                        viewModel.refresh { refreshing = false }
                    },
                    modifier = Modifier.fillMaxSize(),
                ) {
                // The payload has landed: fade and lift the whole screen in
                // once, rather than having it appear fully formed. One
                // animation for the lot, read in the layer phase, so it costs
                // nothing per item.
                val enter = remember { Animatable(0f) }
                LaunchedEffect(Unit) {
                    enter.animateTo(1f, tween(420, easing = FastOutSlowInEasing))
                }

                LazyColumn(
                    state = feed,
                    modifier = Modifier
                        .fillMaxSize()
                        .graphicsLayer {
                            alpha = enter.value
                            translationY = (1f - enter.value) * 26.dp.toPx()
                            // Auto would put the whole feed through a
                            // full-screen offscreen buffer for as long as alpha
                            // is under 1 — during the very first flick, that
                            // is. Modulating instead applies the fade per draw,
                            // which for a fade from nothing looks the same.
                            compositingStrategy = CompositingStrategy.ModulateAlpha
                        }
                ) {
                    item(key = "header", contentType = "header") {
                        HomeCityRow(city = city, onPickRegion = { showRegions = true })
                    }

                    // Sticky, where the city above it is not. Searching is the
                    // one thing a customer may want at any depth of the feed,
                    // and the feed is long enough that finding it meant flinging
                    // back to the top; where they are delivering to is a thing
                    // they set once and read at the top.
                    stickyHeader(key = "search", contentType = "search") {
                        HomeSearchRow(onOpenSearch = onOpenSearch, stuck = stuck)
                    }

                    if (home.banners.isNotEmpty()) {
                        item(key = "banners", contentType = "banners") {
                            Box(Modifier.padding(top = SectionGap)) {
                                BannerCarousel(home.banners, bannerPager, onOpenBanner)
                            }
                        }
                    }

                    categoryGrid(home.categories, onOpenCategory)

                    home.sections.forEach { section ->
                        homeSection(
                            section = section,
                            onOpenProduct = onOpenProduct,
                            onOpenAll = { onOpenListing(section.categorySlug, section.title) },
                            onToggleFavorite = { p -> viewModel.toggleFavorite(p.id, p.isFavorite) },
                            onAddToCart = { p ->
                                if (p.hasVariants) {
                                    picking = p
                                } else {
                                    viewModel.addToCart(p.id) { toast.value = it }
                                }
                            },
                        )
                    }

                    item(key = "tab-bar-spacer", contentType = "spacer") { MbTabBarSpacer() }
                }
                }
            }
            MbToastHost(toast, Modifier.align(Alignment.BottomCenter).padding(bottom = 100.dp))
            picking?.let { card ->
                VariantSheet(
                    card = card,
                    onDismiss = { picking = null },
                    onOpenCart = {
                        picking = null
                        onOpenCart()
                    },
                )
            }
        }
    }

    if (showRegions) {
        RegionPicker(
            current = city,
            onPick = {
                viewModel.setCity(it)
                showRegions = false
            },
            onDismiss = { showRegions = false },
        )
    }
}

/** The 14 delivery regions, as a sheet off the location row. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun RegionPicker(
    current: String,
    onPick: (String) -> Unit,
    onDismiss: () -> Unit,
) {
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
        containerColor = MbTheme.colors.surface,
        shape = MbTheme.shapes.sheet,
    ) {
        Column(Modifier.padding(horizontal = 20.dp)) {
            MbText(stringResource(R.string.hududni_tanlang), MbTheme.type.title2)
            Spacer(Modifier.height(4.dp))
            MbText(
                stringResource(R.string.yetkazish_muddati_va_narxi_hududga_qarab),
                MbTheme.type.meta,
                MbTheme.colors.icon,
            )
            Spacer(Modifier.height(12.dp))
            LazyColumn(Modifier.fillMaxWidth()) {
                items(UZ_REGIONS, key = { it.canonical }) { region ->
                    MbRadioRow(
                        label = stringResource(region.labelRes),
                        // The stored value stays Uzbek in every language, so a
                        // city picked in Russian still matches delivery data.
                        selected = region.canonical == current,
                        onSelect = { onPick(region.canonical) },
                        leading = {
                            MbIcon("pin", size = 18.dp, tint = MbTheme.colors.icon)
                        },
                    )
                    MbDivider(inset = 30.dp)
                }
                item { Spacer(Modifier.height(24.dp)) }
            }
        }
    }
}

@Composable
private fun HomeCityRow(city: String, onPickRegion: () -> Unit) {
    Row(
        Modifier
            .fillMaxWidth()
            .background(MbTheme.colors.surface)
            .padding(start = 14.dp, end = 20.dp, top = 6.dp, bottom = 8.dp)
            .mbClickable(MbTheme.shapes.chip, onClick = onPickRegion)
            .padding(horizontal = 6.dp, vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        MbIcon("pin", size = 16.dp, tint = MbTheme.colors.accent, strokeWidth = 1.9f)
        // The stored city is always Uzbek; show it in the app language.
        MbText(regionLabel(city), MbTheme.type.body.copy(fontWeight = FontWeight.Bold))
        MbIcon(
            "chevron-down",
            size = 18.dp,
            tint = MbTheme.colors.textSecondary,
            strokeWidth = 2f,
        )
    }
}

/**
 * The search pill, which stays at the top while the feed runs under it.
 *
 * Opaque, and the full width of the window: a sticky header is drawn over the
 * list rather than beside it, so anything see-through here shows the products
 * sliding along behind the placeholder.
 */
@Composable
private fun HomeSearchRow(onOpenSearch: () -> Unit, stuck: Boolean) {
    // A shadow under the band rather than a rule, and none at all on the dark
    // theme — the same two decisions a product card makes, for the same two
    // reasons. A hairline is a drawn edge: the eye finds it whether or not it
    // was looking, and this page keeps no edges anywhere else. A shadow is only
    // found when looked for, which is all this has to do — say that the white
    // above is in front of the white below. On the dark theme the band is a
    // step lighter than the page already, and a black gradient over a near
    // black canvas would be nothing but wasted drawing.
    val lift = if (MbTheme.colors.isDark) 0f else 1f
    val depth by animateFloatAsState(
        if (stuck) lift else 0f,
        tween(180, easing = FastOutSlowInEasing),
        label = "searchLift",
    )
    Box(
        Modifier
            .fillMaxWidth()
            .drawBehind {
                if (depth <= 0.01f) return@drawBehind
                val fall = 9.dp.toPx()
                drawRect(
                    brush = Brush.verticalGradient(
                        listOf(Color.Black.copy(alpha = 0.085f * depth), Color.Transparent),
                        startY = size.height,
                        endY = size.height + fall,
                    ),
                    topLeft = Offset(0f, size.height),
                    size = Size(size.width, fall),
                )
            }
            .background(MbTheme.colors.surface)
            // Even above and below: the pill used to take its top margin from
            // the city row it followed, and splitting the two left it pressed
            // against the top of its own band.
            .padding(horizontal = 20.dp, vertical = 10.dp),
    ) {
        MbSearchPill(stringResource(R.string.mahsulot_va_turkumlar_qidirish), onOpenSearch)
    }
}

@Composable
private fun BannerCarousel(
    banners: List<BannerDto>,
    pager: PagerState,
    onClick: (BannerDto) -> Unit,
) {
    // Keyed on settledPage, so the wait restarts every time the carousel comes
    // to rest — including after the customer swipes it themselves, which is
    // what stops it yanking the page away from under their thumb.
    LaunchedEffect(pager.settledPage, banners.size) {
        if (banners.size < 2) return@LaunchedEffect
        delay(4_500)
        // Always the next page, never a modulo back to the first: the pages run
        // far enough in both directions that forward is always available.
        pager.animateScrollToPage(
            page = pager.settledPage + 1,
            animationSpec = tween(700, easing = FastOutSlowInEasing),
        )
    }

    Column {
        HorizontalPager(
            state = pager,
            pageSpacing = 10.dp,
            contentPadding = PaddingValues(horizontal = 12.dp),
        ) { page ->
            BannerCard(
                banner = banners[page % banners.size],
                // A lambda, not a value: read as a value here the card would
                // recompose on every frame of a swipe. Read inside the layer
                // instead, only the drawing is invalidated.
                drift = {
                    (pager.currentPage - page + pager.currentPageOffsetFraction)
                        .coerceIn(-1f, 1f)
                },
                onClick = { onClick(banners[page % banners.size]) },
            )
        }
        Spacer(Modifier.height(10.dp))
        Row(
            Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.Center,
        ) {
            repeat(banners.size) { index ->
                val active = index == pager.currentPage % banners.size
                val width by animateDpAsState(
                    if (active) 14.dp else 3.5.dp,
                    tween(260, easing = FastOutSlowInEasing),
                    label = "dot",
                )
                val color by animateColorAsState(
                    if (active) MbTheme.colors.accent else MbTheme.colors.hairlineStrong,
                    tween(260),
                    label = "dotColor",
                )
                Box(
                    Modifier
                        .padding(horizontal = 2.dp)
                        .size(width = width, height = 3.5.dp)
                        .clip(RoundedCornerShape(2.dp))
                        .background(color)
                )
            }
        }
    }
}

@Composable
private fun BannerCard(banner: BannerDto, drift: () -> Float, onClick: () -> Unit) {
    Row(
        Modifier
            .fillMaxWidth()
            .height(MbTheme.dimens.bannerHeight)
            .clip(MbTheme.shapes.card)
            .background(
                Brush.linearGradient(
                    listOf(banner.gradientFrom.toColor(), banner.gradientTo.toColor())
                )
            )
            .clickable(onClick = onClick)
            .padding(start = 18.dp, end = 14.dp, top = 15.dp, bottom = 15.dp),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Column(Modifier.weight(1f)) {
            MbText(banner.kicker, MbTheme.type.badge, Color.White.copy(alpha = 0.68f), maxLines = 1)
            Spacer(Modifier.weight(1f))
            MbText(banner.title, MbTheme.type.title1, Color.White, maxLines = 2)
            Spacer(Modifier.height(5.dp))
            MbText(banner.subtitle, MbTheme.type.meta, Color.White.copy(alpha = 0.72f), maxLines = 2)
            Spacer(Modifier.height(9.dp))
            Box(
                Modifier
                    .clip(MbTheme.shapes.chip)
                    .background(Color.White)
                    .padding(horizontal = 13.dp, vertical = 7.dp)
            ) {
                MbText(banner.cta, MbTheme.type.meta.copy(
                    fontWeight = androidx.compose.ui.text.font.FontWeight.ExtraBold),
                    MbTheme.colors.heroFrom)
            }
        }
        MbProductImage(
            banner.imageUrl,
            modifier = Modifier
                .width(110.dp)
                .fillMaxSize()
                .graphicsLayer { translationX = drift() * 40.dp.toPx() },
            shape = MbTheme.shapes.tile,
            background = Color.White.copy(alpha = 0.08f),
            // Whole, not cropped to the panel's shape: this box is narrower
            // than the photographs are, so cropping took the sides off them.
            contentScale = ContentScale.Fit,
        )
    }
}

/** The 5x2 quick-link grid, one lazy item per row of five. */
private fun LazyListScope.categoryGrid(
    categories: List<CategoryDto>,
    onClick: (CategoryDto) -> Unit,
) {
    val rows = categories.chunked(5)
    rows.forEachIndexed { index, row ->
        item(key = "categories:$index", contentType = "category-row") {
            val first = index == 0
            val last = index == rows.lastIndex
            val shape = when {
                first && last -> MbTheme.shapes.card
                first -> CardTopShape
                last -> CardBottomShape
                else -> RectangleShape
            }
            Row(
                Modifier
                    .fillMaxWidth()
                    .padding(start = 12.dp, end = 12.dp, top = if (first) SectionGap else 0.dp)
                    .background(MbTheme.colors.surface, shape)
                    .padding(
                        start = 14.dp,
                        end = 14.dp,
                        // 14 dp card padding on the outer rows, plus the 7 dp
                        // every row keeps around itself.
                        top = if (first) 21.dp else 7.dp,
                        bottom = if (last) 21.dp else 7.dp,
                    ),
                horizontalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                row.forEach { category ->
                    CategoryCell(category, onClick, Modifier.weight(1f))
                }
                repeat(5 - row.size) { Spacer(Modifier.weight(1f)) }
            }
        }
    }
}

@Composable
private fun CategoryCell(
    category: CategoryDto,
    onClick: (CategoryDto) -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        // A bare `clickable` presses in a hard rectangle the full width of the
        // cell and the full height of tile plus label — a corner-to-corner slab
        // under a 44 dp rounded tile. The highlight is drawn over the content
        // rather than clipping it, which is what keeps the two-line names off
        // the corner arcs.
        modifier
            .mbPressable(
                MbTheme.shapes.tile,
                MbTheme.colors.ink.copy(alpha = MbPressAlpha),
            ) { onClick(category) }
            .padding(vertical = 4.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        Box(
            Modifier
                .size(MbTheme.dimens.categoryTile)
                .clip(MbTheme.shapes.tile)
                .background(MbTheme.colors.fill),
            contentAlignment = Alignment.Center,
        ) {
            // A photograph where the shop supplied one, the line glyph where
            // it did not — the grid holds both without looking mixed because
            // the tile behind them is the same.
            val image = category.imageUrl
            if (image != null) {
                AsyncImage(
                    model = image.mediaUrl(),
                    contentDescription = null,
                    contentScale = ContentScale.Fit,
                    modifier = Modifier.size(MbTheme.dimens.categoryTile * 0.72f),
                )
            } else {
                MbIcon(category.icon, size = 20.dp)
            }
        }
        MbText(
            category.name,
            MbTheme.type.micro.copy(
                fontWeight = androidx.compose.ui.text.font.FontWeight.SemiBold),
            MbTheme.colors.inkSoft,
            maxLines = 2,
            textAlign = androidx.compose.ui.text.style.TextAlign.Center,
        )
    }
}

/**
 * One home section, emitted as several small lazy items so a scroll frame
 * composes a header or a single product row, never a whole card.
 */
private fun LazyListScope.homeSection(
    section: SectionDto,
    onOpenProduct: (Int) -> Unit,
    onOpenAll: () -> Unit,
    onToggleFavorite: (ProductCardDto) -> Unit,
    onAddToCart: (ProductCardDto) -> Unit,
) {
    when (section.layout) {
        // Two tiles and a header — light enough to stay a single item.
        "deals" -> item(key = section.key, contentType = "deals") {
            MbCard(
                Modifier.padding(start = 12.dp, end = 12.dp, top = SectionGap),
                padding = 16.dp,
            ) {
                SectionHeader(section.title, section.subtitle)
                Spacer(Modifier.height(12.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    section.products.forEach { product ->
                        MbDealTile(
                            title = product.title,
                            price = product.price,
                            oldPrice = product.oldPrice,
                            discountPercent = product.discountPercent,
                            imageUrl = product.imageUrl,
                            inStock = product.inStock,
                            onClick = { onOpenProduct(product.id) },
                            modifier = Modifier.weight(1f),
                        )
                    }
                }
            }
        }

        "grid" -> {
            item(key = "${section.key}:head", contentType = "grid-head") {
                Box(
                    Modifier
                        .fillMaxWidth()
                        .padding(start = 12.dp, end = 12.dp, top = SectionGap)
                        .background(MbTheme.colors.surface, CardTopShape)
                        .padding(14.dp),
                ) {
                    SectionHeader(section.title, section.subtitle)
                }
            }
            val rows = section.products.chunked(2)
            rows.forEachIndexed { index, row ->
                item(key = "${section.key}:row$index", contentType = "grid-row") {
                    val last = index == rows.lastIndex
                    Row(
                        Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 12.dp)
                            .background(
                                MbTheme.colors.surface,
                                if (last) CardBottomShape else RectangleShape,
                            )
                            .padding(
                                start = 14.dp,
                                end = 14.dp,
                                // The last row also carries the card's own
                                // 14 dp bottom padding.
                                bottom = if (last) 30.dp else 16.dp,
                            ),
                        horizontalArrangement = Arrangement.spacedBy(16.dp),
                    ) {
                        row.forEach { product ->
                            MbProductTile(
                                title = product.title,
                                price = product.price,
                                oldPrice = product.oldPrice,
                                discountPercent = product.discountPercent,
                                imageUrl = product.imageUrl,
                                isFavorite = product.isFavorite,
                                inStock = product.inStock,
                                onClick = { onOpenProduct(product.id) },
                                onToggleFavorite = { onToggleFavorite(product) },
                                onAddToCart = { onAddToCart(product) },
                                modifier = Modifier.weight(1f),
                            )
                        }
                        repeat(2 - row.size) { Spacer(Modifier.weight(1f)) }
                    }
                }
            }
        }

        else -> {
            // No panel under a rail, unlike the grid and the deals pair.
            //
            // Those two are bounded: everything they hold is on the screen at
            // once, and a surface drawn around them says where they stop. A rail
            // does not stop — it runs off the side of the screen, and a box
            // around something that leaves the box was the reason the third card
            // read as a card that would not fit rather than as one more card
            // along. So the heading sits on the page and the tiles run to the
            // edges, which is also where the width they had been losing to two
            // sets of padding went.
            item(key = "${section.key}:head", contentType = "rail-head") {
                Box(
                    Modifier
                        .fillMaxWidth()
                        .padding(start = RailEdge, end = RailEdge, top = SectionGap, bottom = 12.dp),
                ) {
                    SectionHeader(
                        title = section.title,
                        subtitle = section.subtitle,
                        actionLabel = stringResource(R.string.barchasi),
                        onAction = onOpenAll,
                    )
                }
            }
            item(key = "${section.key}:rail", contentType = "rail-list") {
                LazyRow(
                    Modifier
                        .fillMaxWidth()
                        .padding(bottom = 4.dp),
                    contentPadding = PaddingValues(horizontal = RailEdge),
                    horizontalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    items(section.products, key = { it.id }, contentType = { "rail-tile" }) { product ->
                        MbRailTile(
                            title = product.title,
                            price = product.price,
                            oldPrice = product.oldPrice,
                            discountPercent = product.discountPercent,
                            imageUrl = product.imageUrl,
                            inStock = product.inStock,
                            onClick = { onOpenProduct(product.id) },
                        )
                    }
                }
            }
        }
    }
}
