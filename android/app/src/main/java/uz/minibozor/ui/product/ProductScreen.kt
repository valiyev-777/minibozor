package uz.minibozor.ui.product

import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalContext
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.animation.slideOutVertically
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.fadeOut
import androidx.compose.animation.fadeIn
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.runtime.derivedStateOf
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.runtime.Composable
import androidx.compose.foundation.layout.offset
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.res.stringResource
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.zIndex
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.RectangleShape
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import uz.minibozor.R
import uz.minibozor.core.design.MbText
import uz.minibozor.core.design.MbTheme
import uz.minibozor.core.design.component.MbExpandableSection
import uz.minibozor.core.design.component.MbCollapsibleText
import uz.minibozor.core.design.component.MbCard
import uz.minibozor.core.design.component.MbDivider
import uz.minibozor.core.design.component.MbErrorState
import uz.minibozor.core.design.component.MbKeyValueRow
import uz.minibozor.core.design.component.MbRating
import uz.minibozor.core.design.component.MbSizeChip
import uz.minibozor.core.design.component.MbStatusPill
import uz.minibozor.core.design.component.SectionHeader
import uz.minibozor.core.design.icon.MbIcon
import uz.minibozor.core.util.toColor
import uz.minibozor.ui.common.MbToastHost
import uz.minibozor.ui.common.rememberToast
import uz.minibozor.ui.product.component.ReviewRow

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

/** Screen 14 — Mahsulot. */
@OptIn(ExperimentalLayoutApi::class)
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

    // Every motion on this screen answers the scroll; nothing plays on its own.
    val product = state.product
    val listState = rememberLazyListState()

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

    // Where the bar's own bottom edge sits, and how far past it the name
    // travels before the bar has it entirely.
    val barBottomPx = statusBarPx + with(density) { 56.dp.toPx() }
    val handoverPx = with(density) { 20.dp.toPx() }
    val cardPaddingPx = with(density) { 16.dp.toPx() }

    /**
     * The height of the name where it sits on the page.
     *
     * Reported by the card rather than assumed, because a long name wraps to
     * two lines and a short one does not — and this decides when the bar is
     * allowed to show the name, so being a line out puts it on screen twice.
     * onSizeChanged fires when the text rewraps, not on every scroll frame.
     */
    var titleHeightPx by remember { mutableFloatStateOf(0f) }

    /**
     * How far the name has been handed from the page to the bar, 0..1.
     *
     * Measured against the name itself, not the card holding it. Keying it to
     * the card's top edge handed the name over while the name was still in
     * plain sight a padding's distance below the bar — which is the same fault
     * as driving it from the photo, one step smaller.
     */
    val handover by remember {
        derivedStateOf {
            val identity = listState.layoutInfo.visibleItemsInfo
                .firstOrNull { it.key == "identity" }
            if (identity == null) {
                if (listState.firstVisibleItemIndex > 0) 1f else 0f
            } else {
                val nameBottom = identity.offset + cardPaddingPx + titleHeightPx
                ((barBottomPx - nameBottom) / handoverPx).coerceIn(0f, 1f)
            }
        }
    }

    val heroPager = rememberPagerState(
        pageCount = { maxOf(product?.images?.size ?: 1, 1) },
    )

    /** Once the bar is showing the price, the buy bar drops its own. */
    val priceInHeader by remember { derivedStateOf { handover > 0.6f } }

    // The hero's ground follows the theme now, so the system clock needs no
    // special handling here: it used to be forced dark because the hero was
    // white even on the dark theme.

    val context = LocalContext.current

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
                    LazyColumn(
                        Modifier.fillMaxSize(),
                        state = listState,
                        // Room at the bottom for the buy bar to float over.
                        contentPadding = PaddingValues(bottom = 108.dp),
                        // No blanket spacing: the first panel has to butt
                        // straight up against the photograph, or the gap is
                        // still uncovered at the moment the list stops drawing
                        // the photograph and shows as a strip of bare page.
                        // Every panel after it carries its own gap instead.
                    ) {
                        // The photo runs edge to edge under the status bar and
                        // closes away behind the content as you scroll past it.
                        item(key = "hero") {
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
                            )
                        }

                        // Grouped by what a section is for rather than one
                        // card each: "what is this", "which one", "the small
                        // print". Five floating panels between the photo and
                        // the reviews read as clutter; one panel for the lot
                        // would just be a long box with no seams where the
                        // subject changes.
                        item(key = "identity") {
                            // Above the photo, and it overlaps it because the
                            // photo hangs back — so the panel is seen crossing
                            // in front of the picture rather than arriving
                            // once the picture has gone.
                            MbCard(shape = RectangleShape, modifier = Modifier.zIndex(1f)) {
                                // No price here: it is in the buy bar a thumb's
                                // reach away and in the bar once the photo
                                // closes, so a third copy is just noise.
                                MbText(
                                    product.title,
                                    MbTheme.type.title2,
                                    modifier = Modifier.onSizeChanged {
                                        titleHeightPx = it.height.toFloat()
                                    },
                                )
                                if (product.subtitle.isNotBlank()) {
                                    Spacer(Modifier.height(4.dp))
                                    MbText(
                                        product.subtitle,
                                        MbTheme.type.bodySmall,
                                        MbTheme.colors.textTertiary,
                                    )
                                }
                                Spacer(Modifier.height(10.dp))
                                Row(
                                    verticalAlignment = Alignment.CenterVertically,
                                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                                ) {
                                    MbRating(product.rating, product.reviewsCount)
                                    if (product.isOriginal) {
                                        MbStatusPill(
                                            stringResource(R.string.original),
                                            MbTheme.colors.successBg,
                                            MbTheme.colors.success,
                                        )
                                    }
                                }
                                if (product.description.isNotBlank()) {
                                    Spacer(Modifier.height(14.dp))
                                    MbDivider()
                                    Spacer(Modifier.height(14.dp))
                                    SectionHeader(stringResource(R.string.tavsif))
                                    Spacer(Modifier.height(10.dp))
                                    MbCollapsibleText(product.description)
                                }
                            }
                        }

                        val sizes = product.variants.filter { it.kind == "size" }
                        val colors = product.variants.filter { it.kind == "color" }
                        if (sizes.isNotEmpty() || colors.isNotEmpty()) {
                            item(key = "options") {
                                MbCard(shape = RectangleShape, modifier = SectionGap) {
                                    if (sizes.isNotEmpty()) {
                                        SectionHeader(
                                            stringResource(R.string.olcham),
                                            stringResource(R.string.olchamlar_jadvali),
                                        )
                                        Spacer(Modifier.height(12.dp))
                                        FlowRow(
                                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                                            verticalArrangement = Arrangement.spacedBy(8.dp),
                                        ) {
                                            sizes.forEach { variant ->
                                                MbSizeChip(
                                                    label = variant.label,
                                                    selected = variant.id == state.selectedSizeId,
                                                    enabled = variant.inStock,
                                                    onClick = { viewModel.selectSize(variant.id) },
                                                )
                                            }
                                        }
                                    }
                                    if (sizes.isNotEmpty() && colors.isNotEmpty()) {
                                        Spacer(Modifier.height(14.dp))
                                        MbDivider()
                                        Spacer(Modifier.height(14.dp))
                                    }
                                    if (colors.isNotEmpty()) {
                                        SectionHeader(stringResource(R.string.rang))
                                        Spacer(Modifier.height(12.dp))
                                        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                                            colors.forEach { variant ->
                                                ColorSwatch(
                                                    hex = variant.value,
                                                    label = variant.label,
                                                    selected = variant.id == state.selectedColorId,
                                                    onClick = { viewModel.selectColor(variant.id) },
                                                )
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        item(key = "smallprint") {
                            MbCard(shape = RectangleShape, modifier = SectionGap) {
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
                                            stringResource(
                                                R.string.sotuvchi_va_qoldiq,
                                                product.seller,
                                                product.stockLeft,
                                            ),
                                        )
                                    }
                                }
                                if (product.specs.isNotEmpty()) {
                                    Spacer(Modifier.height(14.dp))
                                    MbDivider()
                                    Spacer(Modifier.height(14.dp))
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
                                }
                            }
                        }

                        item {
                            MbCard(shape = RectangleShape, modifier = SectionGap) {
                                SectionHeader(
                                    title = stringResource(R.string.sharhlar),
                                    subtitle = state.summary?.let { pluralStringResource(R.plurals.n_items, it.total, it.total) },
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

                        if (state.similar.isNotEmpty()) {
                            item(key = RecommendationsKey) {
                                Recommendations(
                                    products = state.similar,
                                    onOpenProduct = onOpenProduct,
                                    modifier = SectionGap,
                                )
                            }
                        }
                    }
                }
            }
            // Over the photo: three circular buttons that stay put while the
            // bar grows a surface under them, then the name and price arrive.
            ProductChrome(
                product = product,
                handover = { handover },
                onBack = onBack,
                onToggleFavorite = viewModel::toggleFavorite,
                onShare = { product?.let { share(context, it) } },
            )

            // Always there. The price inside it stands down once the bar at the
            // top has taken it over, and the button widens into the room — but
            // the way to buy the thing never leaves the screen.
            AnimatedVisibility(
                visible = product != null,
                enter = slideInVertically { it } + fadeIn(),
                exit = slideOutVertically { it } + fadeOut(),
                modifier = Modifier.align(Alignment.BottomCenter),
            ) {
                product?.let {
                    BuyBar(
                        product = it,
                        adding = state.adding,
                        line = cartLine,
                        showPrice = !priceInHeader,
                        onAdd = { viewModel.addToCart { message -> toast.value = message } },
                        onSetQuantity = viewModel::setCartQuantity,
                        onOpenCart = onOpenCart,
                    )
                }
            }

            MbToastHost(toast, Modifier.align(Alignment.BottomCenter).padding(bottom = 96.dp))
        }
}

@Composable
private fun ColorSwatch(hex: String, label: String, selected: Boolean, onClick: () -> Unit) {
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(6.dp),
        modifier = Modifier.clickable(onClick = onClick),
    ) {
        Box(
            Modifier
                .size(40.dp)
                .clip(CircleShape)
                .background(
                    if (selected) MbTheme.colors.ink else MbTheme.colors.border
                )
                .padding(if (selected) 3.dp else 1.dp)
                .clip(CircleShape)
                .background(hex.toColor(MbTheme.colors.fill))
        )
        MbText(label, MbTheme.type.micro, MbTheme.colors.textSecondary)
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
