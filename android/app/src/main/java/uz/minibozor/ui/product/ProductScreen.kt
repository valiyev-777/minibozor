package uz.minibozor.ui.product

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
import androidx.compose.animation.core.tween
import androidx.compose.animation.core.animateDpAsState
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.animateColorAsState
import androidx.compose.ui.graphics.graphicsLayer
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
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.runtime.Composable
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.spring
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.offset
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.draw.scale
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.delay
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.RectangleShape
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import uz.minibozor.R
import uz.minibozor.core.design.MbText
import uz.minibozor.core.design.MbTheme
import uz.minibozor.core.design.mbTap
import uz.minibozor.core.design.component.MbBottomBar
import uz.minibozor.core.design.component.MbCard
import uz.minibozor.core.design.component.MbDivider
import uz.minibozor.core.design.component.MbErrorState
import uz.minibozor.core.design.component.MbKeyValueRow
import uz.minibozor.core.design.component.MbLoading
import uz.minibozor.core.design.component.MbPriceRow
import uz.minibozor.core.design.component.MbPrimaryButton
import uz.minibozor.core.design.component.MbProductImage
import uz.minibozor.core.design.component.MbRailTile
import uz.minibozor.core.design.component.MbRating
import uz.minibozor.core.design.component.MbScreen
import uz.minibozor.core.design.component.MbSizeChip
import uz.minibozor.core.design.component.MbStatusPill
import uz.minibozor.core.design.component.MbTopBar
import uz.minibozor.core.design.component.SectionHeader
import uz.minibozor.core.design.icon.MbIcon
import uz.minibozor.core.util.toColor
import uz.minibozor.ui.common.MbToastHost
import uz.minibozor.ui.common.rememberToast
import uz.minibozor.ui.product.component.ReviewRow

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
    val heroHeight = heroHeight()
    val closePx = with(density) { heroHeight.toPx() * 0.55f }

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

    /** Once the header row is showing the price, the buy bar drops its own. */
    val priceInHeader by remember {
        derivedStateOf { closed > 0.6f }
    }

    /** The buy bar steps aside once the recommendations reach it. */
    val atRecommendations by remember {
        derivedStateOf {
            listState.layoutInfo.visibleItemsInfo.any { it.key == RecommendationsKey }
        }
    }

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
                        verticalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        // The photo runs edge to edge under the status bar and
                        // closes away behind the content as you scroll past it.
                        item(key = "hero") {
                            Hero(
                                images = product.images,
                                badge = product.badge,
                                closed = { closed },
                            )
                        }

                        item {
                            MbCard(Modifier.padding(horizontal = 12.dp)) {
                                // No price here: it is in the buy bar a thumb's
                                // reach away and in the bar once the photo
                                // closes, so a third copy is just noise.
                                MbText(product.title, MbTheme.type.title2)
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
                            }
                        }

                        if (product.description.isNotBlank()) {
                            item {
                                MbCard(Modifier.padding(horizontal = 12.dp)) {
                                    SectionHeader(stringResource(R.string.tavsif))
                                    Spacer(Modifier.height(10.dp))
                                    MbText(
                                        product.description,
                                        MbTheme.type.bodySmall,
                                        MbTheme.colors.inkSoft,
                                    )
                                }
                            }
                        }

                        val sizes = product.variants.filter { it.kind == "size" }
                        if (sizes.isNotEmpty()) {
                            item {
                                MbCard(Modifier.padding(horizontal = 12.dp)) {
                                    SectionHeader(stringResource(R.string.olcham), stringResource(R.string.olchamlar_jadvali))
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
                            }
                        }

                        val colors = product.variants.filter { it.kind == "color" }
                        if (colors.isNotEmpty()) {
                            item {
                                MbCard(Modifier.padding(horizontal = 12.dp)) {
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

                        item {
                            MbCard(Modifier.padding(horizontal = 12.dp)) {
                                DeliveryRow("box", stringResource(R.string.yetkazish), product.deliveryNote)
                                MbDivider()
                                DeliveryRow(
                                    "ret",
                                    stringResource(R.string.qaytarish),
                                    stringResource(R.string.qaytarish_14_kun_ichida_qadoq_butun_bolsa),
                                )
                                if (product.warranty != null) {
                                    MbDivider()
                                    DeliveryRow("gear", stringResource(R.string.kafolat), product.warranty)
                                }
                                MbDivider()
                                DeliveryRow(
                                    "basket",
                                    stringResource(R.string.sotuvchi),
                                    stringResource(R.string.sotuvchi_va_qoldiq, product.seller, product.stockLeft),
                                )
                            }
                        }

                        if (product.specs.isNotEmpty()) {
                            item {
                                MbCard(Modifier.padding(horizontal = 12.dp)) {
                                    SectionHeader(stringResource(R.string.xususiyatlari))
                                    Spacer(Modifier.height(4.dp))
                                    product.specs.forEach { MbKeyValueRow(it.key, it.value) }
                                }
                            }
                        }

                        item {
                            MbCard(Modifier.padding(horizontal = 12.dp)) {
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
                closed = { closed },
                onBack = onBack,
                onToggleFavorite = viewModel::toggleFavorite,
                onShare = { product?.let { share(context, it) } },
            )

            // Steps aside when the recommendations reach it, so the rail can
            // take the width the price was using.
            AnimatedVisibility(
                visible = product != null && !atRecommendations,
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
