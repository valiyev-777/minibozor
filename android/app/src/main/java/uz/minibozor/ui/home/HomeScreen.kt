package uz.minibozor.ui.home

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.text.font.FontWeight
import uz.minibozor.core.design.component.MbDivider
import uz.minibozor.core.design.component.MbRadioRow
import uz.minibozor.core.design.mbClickable
import uz.minibozor.core.util.UZ_REGIONS
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import uz.minibozor.core.design.MbText
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
import uz.minibozor.ui.common.MbToastHost
import uz.minibozor.ui.common.UiStateContent
import uz.minibozor.ui.common.rememberToast

/**
 * Screen 07. One request fills the whole page: banners, the 5x2 category grid,
 * a deals pair, a two-column recommendation grid and two horizontal rails.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(
    onOpenSearch: () -> Unit,
    onOpenCategory: (CategoryDto) -> Unit,
    onOpenBanner: (BannerDto) -> Unit,
    onOpenProduct: (Int) -> Unit,
    onOpenListing: (category: String?, title: String) -> Unit,
    viewModel: HomeViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val city by viewModel.city.collectAsStateWithLifecycle()
    val toast = rememberToast()
    var showRegions by remember { mutableStateOf(false) }
    var refreshing by remember { mutableStateOf(false) }

    MbScreen { padding ->
        Box(Modifier.fillMaxSize()) {
            UiStateContent(
                state = state,
                onRetry = viewModel::load,
                modifier = Modifier.padding(padding),
            ) { home ->
                PullToRefreshBox(
                    isRefreshing = refreshing,
                    onRefresh = {
                        refreshing = true
                        viewModel.refresh { refreshing = false }
                    },
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(padding),
                ) {
                LazyColumn(
                    Modifier.fillMaxSize(),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    item {
                        HomeHeader(
                            city = city,
                            onOpenSearch = onOpenSearch,
                            onPickRegion = { showRegions = true },
                        )
                    }

                    if (home.banners.isNotEmpty()) {
                        item { BannerCarousel(home.banners, onOpenBanner) }
                    }

                    item {
                        CategoryGrid(
                            categories = home.categories,
                            onClick = onOpenCategory,
                            modifier = Modifier.padding(horizontal = 12.dp),
                        )
                    }

                    home.sections.forEach { section ->
                        item(key = section.key) {
                            HomeSection(
                                section = section,
                                onOpenProduct = onOpenProduct,
                                onOpenAll = { onOpenListing(section.categorySlug, section.title) },
                                onToggleFavorite = { p -> viewModel.toggleFavorite(p.id, p.isFavorite) },
                                onAddToCart = { p ->
                                    viewModel.addToCart(p.id) { toast.value = it }
                                },
                            )
                        }
                    }

                    item { MbTabBarSpacer() }
                }
                }
            }
            MbToastHost(toast, Modifier.align(Alignment.BottomCenter).padding(bottom = 100.dp))
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
            MbText("Hududni tanlang", MbTheme.type.title2)
            Spacer(Modifier.height(4.dp))
            MbText(
                "Yetkazish muddati va narxi hududga qarab o'zgaradi",
                MbTheme.type.meta,
                MbTheme.colors.icon,
            )
            Spacer(Modifier.height(12.dp))
            LazyColumn(Modifier.fillMaxWidth()) {
                items(UZ_REGIONS, key = { it }) { region ->
                    MbRadioRow(
                        label = region,
                        selected = region == current,
                        onSelect = { onPick(region) },
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
private fun HomeHeader(
    city: String,
    onOpenSearch: () -> Unit,
    onPickRegion: () -> Unit,
) {
    Column(Modifier.background(MbTheme.colors.surface)) {
        Row(
            Modifier
                .padding(start = 14.dp, end = 20.dp, top = 6.dp, bottom = 8.dp)
                .mbClickable(MbTheme.shapes.chip, onClick = onPickRegion)
                .padding(horizontal = 6.dp, vertical = 4.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            MbIcon("pin", size = 16.dp, tint = MbTheme.colors.accent, strokeWidth = 1.9f)
            MbText(city, MbTheme.type.body.copy(fontWeight = FontWeight.Bold))
            MbIcon(
                "chevron-down",
                size = 18.dp,
                tint = MbTheme.colors.textSecondary,
                strokeWidth = 2f,
            )
        }
        Box(Modifier.padding(start = 20.dp, end = 20.dp, bottom = 14.dp)) {
            MbSearchPill("Mahsulot va turkumlar qidirish", onOpenSearch)
        }
    }
}

@Composable
private fun BannerCarousel(banners: List<BannerDto>, onClick: (BannerDto) -> Unit) {
    val pager = rememberPagerState(pageCount = { banners.size })
    Column {
        HorizontalPager(
            state = pager,
            pageSpacing = 10.dp,
            contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 12.dp),
        ) { page ->
            BannerCard(banners[page]) { onClick(banners[page]) }
        }
        Spacer(Modifier.height(10.dp))
        Row(
            Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.Center,
        ) {
            repeat(banners.size) { index ->
                val active = index == pager.currentPage
                Box(
                    Modifier
                        .padding(horizontal = 2.dp)
                        .size(width = if (active) 14.dp else 3.5.dp, height = 3.5.dp)
                        .clip(RoundedCornerShape(2.dp))
                        .background(
                            if (active) MbTheme.colors.accent else MbTheme.colors.hairlineStrong
                        )
                )
            }
        }
    }
}

@Composable
private fun BannerCard(banner: BannerDto, onClick: () -> Unit) {
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
                .fillMaxSize(),
            shape = MbTheme.shapes.tile,
            background = Color.White.copy(alpha = 0.08f),
            contentScale = ContentScale.Crop,
        )
    }
}

@Composable
private fun CategoryGrid(
    categories: List<CategoryDto>,
    onClick: (CategoryDto) -> Unit,
    modifier: Modifier = Modifier,
) {
    MbCard(modifier, padding = 14.dp) {
        categories.chunked(5).forEach { row ->
            Row(
                Modifier
                    .fillMaxWidth()
                    .padding(vertical = 7.dp),
                horizontalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                row.forEach { category ->
                    Column(
                        Modifier
                            .weight(1f)
                            .clickable { onClick(category) },
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
                            MbIcon(category.icon, size = 20.dp)
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
                repeat(5 - row.size) { Spacer(Modifier.weight(1f)) }
            }
        }
    }
}

@Composable
private fun HomeSection(
    section: SectionDto,
    onOpenProduct: (Int) -> Unit,
    onOpenAll: () -> Unit,
    onToggleFavorite: (ProductCardDto) -> Unit,
    onAddToCart: (ProductCardDto) -> Unit,
) {
    when (section.layout) {
        "deals" -> MbCard(Modifier.padding(horizontal = 12.dp), padding = 16.dp) {
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
                        onClick = { onOpenProduct(product.id) },
                        modifier = Modifier.weight(1f),
                    )
                }
            }
        }

        "grid" -> MbCard(Modifier.padding(horizontal = 12.dp), padding = 14.dp) {
            SectionHeader(section.title, section.subtitle)
            Spacer(Modifier.height(14.dp))
            section.products.chunked(2).forEach { row ->
                Row(
                    Modifier.padding(bottom = 16.dp),
                    horizontalArrangement = Arrangement.spacedBy(16.dp),
                ) {
                    row.forEach { product ->
                        MbProductTile(
                            title = product.title,
                            price = product.price,
                            oldPrice = product.oldPrice,
                            discountPercent = product.discountPercent,
                            imageUrl = product.imageUrl,
                            rating = product.rating,
                            reviewsCount = product.reviewsCount,
                            badge = product.badge,
                            isFavorite = product.isFavorite,
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

        else -> MbCard(Modifier.padding(horizontal = 12.dp), padding = 0.dp) {
            SectionHeader(
                title = section.title,
                subtitle = section.subtitle,
                actionLabel = "Barchasi",
                onAction = onOpenAll,
                modifier = Modifier.padding(start = 16.dp, end = 16.dp, top = 16.dp),
            )
            LazyRow(
                Modifier.padding(top = 12.dp, bottom = 16.dp),
                contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 16.dp),
                horizontalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                items(section.products, key = { it.id }) { product ->
                    MbRailTile(
                        title = product.title,
                        price = product.price,
                        discountPercent = product.discountPercent,
                        imageUrl = product.imageUrl,
                        onClick = { onOpenProduct(product.id) },
                    )
                }
            }
        }
    }
}
