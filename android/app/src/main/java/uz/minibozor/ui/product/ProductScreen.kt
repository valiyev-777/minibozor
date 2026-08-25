package uz.minibozor.ui.product

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
    val cartCount by viewModel.cartCount.collectAsStateWithLifecycle()
    val toast = rememberToast()
    LaunchedEffect(productId) { viewModel.load(productId) }

    // A short pulse on the header cart is the feedback that lets someone add and
    // keep browsing without waiting for a toast at the far end of the screen.
    var pulse by remember { mutableStateOf(false) }
    var seenCount by remember { mutableIntStateOf(-1) }
    LaunchedEffect(cartCount) {
        if (seenCount >= 0 && cartCount > seenCount) {
            pulse = true
            delay(320)
            pulse = false
        }
        seenCount = cartCount
    }
    val cartScale by animateFloatAsState(
        targetValue = if (pulse) 1.35f else 1f,
        animationSpec = spring(dampingRatio = 0.35f, stiffness = 900f),
        label = "cartPulse",
    )

    MbScreen(
        topBar = {
            MbTopBar(
                title = "",
                onBack = onBack,
                action = {
                    state.product?.let { product ->
                        MbIcon(
                            "heart",
                            size = 22.dp,
                            tint = if (product.isFavorite) MbTheme.colors.danger
                            else MbTheme.colors.ink,
                            strokeWidth = 1.9f,
                            filled = product.isFavorite,
                            modifier = Modifier.mbTap { viewModel.toggleFavorite() },
                        )
                    }
                    Box(contentAlignment = Alignment.TopEnd) {
                        MbIcon(
                            "cart",
                            size = 22.dp,
                            tint = MbTheme.colors.ink,
                            strokeWidth = 1.9f,
                            modifier = Modifier
                                .scale(cartScale)
                                .mbTap(onClick = onOpenCart),
                        )
                        if (cartCount > 0) {
                            MbText(
                                if (cartCount > 99) "99+" else cartCount.toString(),
                                MbTheme.type.micro.copy(fontSize = 8.5.sp),
                                Color.White,
                                modifier = Modifier
                                    .offset(x = 7.dp, y = (-6).dp)
                                    .defaultMinSize(minWidth = 15.dp)
                                    .clip(CircleShape)
                                    .background(MbTheme.colors.danger)
                                    .padding(horizontal = 4.dp, vertical = 1.dp),
                                textAlign = TextAlign.Center,
                            )
                        }
                    }
                },
            )
        },
        bottomBar = {
            val product = state.product
            if (product != null) {
                MbBottomBar {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) {
                            MbPriceRow(product.price, product.oldPrice, product.discountPercent)
                        }
                        Spacer(Modifier.size(14.dp))
                        MbPrimaryButton(
                            text = if (product.inStock) stringResource(R.string.savatga) else stringResource(R.string.mavjud_emas),
                            onClick = {
                                viewModel.addToCart { message ->
                                    toast.value = message
                                }
                            },
                            enabled = product.inStock,
                            loading = state.adding,
                            modifier = Modifier.weight(1.2f),
                        )
                    }
                }
            }
        },
    ) { padding ->
        Box(Modifier.fillMaxSize()) {
            when {
                state.loading -> MbLoading(Modifier.padding(padding))
                state.error != null -> MbErrorState(state.error!!, viewModel::retry, Modifier.padding(padding))
                else -> state.product?.let { product ->
                    LazyColumn(
                        Modifier
                            .fillMaxSize()
                            .padding(padding),
                        contentPadding = PaddingValues(bottom = 20.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        item { Gallery(product.images, product.badge) }

                        item {
                            MbCard(Modifier.padding(horizontal = 12.dp)) {
                                MbPriceRow(
                                    product.price,
                                    product.oldPrice,
                                    product.discountPercent,
                                    priceStyle = MbTheme.type.display,
                                )
                                Spacer(Modifier.height(8.dp))
                                MbText(product.title, MbTheme.type.title3)
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
                            item {
                                MbCard(Modifier.padding(horizontal = 12.dp), padding = 0.dp) {
                                    SectionHeader(
                                        stringResource(R.string.oxshash_tovarlar),
                                        modifier = Modifier.padding(16.dp),
                                    )
                                    LazyRow(
                                        contentPadding = PaddingValues(horizontal = 16.dp),
                                        horizontalArrangement = Arrangement.spacedBy(10.dp),
                                        modifier = Modifier.padding(bottom = 16.dp),
                                    ) {
                                        items(state.similar, key = { it.id }) { item ->
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
                        }
                    }
                }
            }
            MbToastHost(toast, Modifier.align(Alignment.BottomCenter).padding(bottom = 90.dp))
        }
    }
}

@Composable
private fun Gallery(images: List<String>, badge: String?) {
    val pager = rememberPagerState(pageCount = { maxOf(images.size, 1) })
    Box(Modifier.background(MbTheme.colors.surface)) {
        HorizontalPager(pager) { page ->
            MbProductImage(
                images.getOrNull(page),
                modifier = Modifier
                    .fillMaxWidth()
                    .aspectRatio(1f),
                shape = RectangleShape,
                background = MbTheme.colors.photoWarm,
            )
        }
        if (badge != null) {
            MbStatusPill(
                badge,
                MbTheme.colors.ink.copy(alpha = 0.8f),
                Color.White,
                Modifier
                    .align(Alignment.TopStart)
                    .padding(14.dp),
            )
        }
        if (images.size > 1) {
            Row(
                Modifier
                    .align(Alignment.BottomCenter)
                    .padding(bottom = 14.dp),
                horizontalArrangement = Arrangement.spacedBy(5.dp),
            ) {
                repeat(images.size) { index ->
                    Box(
                        Modifier
                            .size(if (index == pager.currentPage) 18.dp else 6.dp, 6.dp)
                            .clip(CircleShape)
                            .background(
                                if (index == pager.currentPage) MbTheme.colors.ink
                                else MbTheme.colors.hairline
                            )
                    )
                }
            }
        }
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
