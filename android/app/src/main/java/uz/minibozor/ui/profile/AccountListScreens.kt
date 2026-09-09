package uz.minibozor.ui.profile

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
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.lazy.items
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.setValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.mutableStateOf
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.LifecycleResumeEffect
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import uz.minibozor.R
import uz.minibozor.core.design.MbText
import uz.minibozor.core.design.MbTheme
import uz.minibozor.core.design.component.MbCard
import uz.minibozor.core.design.component.MbDivider
import uz.minibozor.core.design.component.MbEmptyState
import uz.minibozor.core.design.component.MbListRow
import uz.minibozor.core.design.component.MbLoading
import uz.minibozor.core.design.component.MbProductTile
import uz.minibozor.core.design.component.MbScreen
import uz.minibozor.core.design.component.MbStatusPill
import uz.minibozor.core.design.component.MbTopBar
import uz.minibozor.core.design.icon.MbIcon
import uz.minibozor.ui.common.MbToastHost
import uz.minibozor.ui.common.rememberToast
import uz.minibozor.ui.product.VariantSheet
import uz.minibozor.data.remote.dto.ProductCardDto
import uz.minibozor.ui.product.component.ReviewRow

@Composable
fun AddressesScreen(
    onBack: () -> Unit,
    onAddAddress: () -> Unit,
    viewModel: AddressesViewModel = hiltViewModel(),
) {
    val addresses by viewModel.addresses.collectAsStateWithLifecycle()

    LifecycleResumeEffect(Unit) {
        viewModel.load()
        onPauseOrDispose {}
    }

    MbScreen(topBar = { MbTopBar(stringResource(R.string.manzillarim), onBack = onBack) }) { padding ->
        LazyColumn(
            Modifier
                .fillMaxSize()
                .padding(padding),
            contentPadding = PaddingValues(12.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            items(addresses, key = { it.id }) { address ->
                MbCard {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Box(
                            Modifier
                                .size(38.dp)
                                .clip(MbTheme.shapes.field)
                                .background(MbTheme.colors.fill),
                            contentAlignment = Alignment.Center,
                        ) {
                            MbIcon(address.icon, size = 18.dp)
                        }
                        Spacer(Modifier.size(12.dp))
                        MbText(
                            address.title,
                            MbTheme.type.body.copy(
                                fontWeight = androidx.compose.ui.text.font.FontWeight.Bold),
                        )
                        Spacer(Modifier.size(8.dp))
                        if (address.badge != null) {
                            MbStatusPill(
                                address.badge,
                                if (address.isDefault) MbTheme.colors.accentTint
                                else MbTheme.colors.fill,
                                if (address.isDefault) MbTheme.colors.accent
                                else MbTheme.colors.textSecondary,
                            )
                        }
                        Spacer(Modifier.weight(1f))
                        MbText(
                            stringResource(R.string.ochirish),
                            MbTheme.type.caption,
                            MbTheme.colors.danger,
                            modifier = Modifier.clickable { viewModel.delete(address.id) },
                        )
                    }
                    Spacer(Modifier.height(10.dp))
                    MbText(address.line, MbTheme.type.bodySmall, MbTheme.colors.inkSoft)
                    if (address.meta.isNotBlank()) {
                        MbText(address.meta, MbTheme.type.meta, MbTheme.colors.icon)
                    }
                }
            }

            item {
                MbCard(padding = 6.dp) {
                    MbListRow(
                        label = stringResource(R.string.yangi_manzil_qoshish),
                        glyph = "pin",
                        tint = MbTheme.colors.accent,
                        onClick = onAddAddress,
                        contentPadding = 10.dp,
                    )
                }
            }
        }
    }
}

/** Screen 34 — Sharhlarim. */
@Composable
fun MyReviewsScreen(
    onBack: () -> Unit,
    onOpenProduct: (Int) -> Unit,
    viewModel: MyReviewsViewModel = hiltViewModel(),
) {
    val reviews by viewModel.reviews.collectAsStateWithLifecycle()

    MbScreen(topBar = { MbTopBar(stringResource(R.string.sharhlarim), onBack = onBack) }) { padding ->
        if (reviews.isEmpty()) {
            MbEmptyState(
                glyph = "star",
                title = stringResource(R.string.hali_sharh_yozmagansiz),
                message = stringResource(R.string.yetkazilgan_tovarlarga_sharh_qoldiring),
                modifier = Modifier.padding(padding),
            )
            return@MbScreen
        }

        LazyColumn(
            Modifier
                .fillMaxSize()
                .padding(padding),
            contentPadding = PaddingValues(12.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            items(reviews, key = { it.id }) { review ->
                MbCard {
                    review.product?.let { product ->
                        Row(
                            Modifier.clickable { onOpenProduct(product.id) },
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            MbText(
                                product.title,
                                MbTheme.type.caption,
                                MbTheme.colors.inkSoft,
                                maxLines = 1,
                                modifier = Modifier.weight(1f),
                            )
                            MbStatusPill(
                                if (review.status == "published") stringResource(R.string.e_lon_qilindi)
                                else stringResource(R.string.tekshirilmoqda),
                                if (review.status == "published") MbTheme.colors.successBg
                                else MbTheme.colors.warningBg,
                                if (review.status == "published") MbTheme.colors.success
                                else MbTheme.colors.warning,
                            )
                        }
                        MbDivider(Modifier.padding(vertical = 12.dp))
                    }
                    ReviewRow(review, onLike = null)
                    Spacer(Modifier.height(10.dp))
                    MbText(
                        stringResource(R.string.ochirish),
                        MbTheme.type.caption,
                        MbTheme.colors.danger,
                        modifier = Modifier.clickable { viewModel.delete(review.id) },
                    )
                }
            }
        }
    }
}

/** Screen 35 — Sevimlilar. */
@Composable
fun FavoritesScreen(
    onBack: () -> Unit,
    onOpenProduct: (Int) -> Unit,
    onStartShopping: () -> Unit,
    onOpenCart: () -> Unit,
    viewModel: FavoritesViewModel = hiltViewModel(),
) {
    val items by viewModel.items.collectAsStateWithLifecycle()
    val loading by viewModel.loading.collectAsStateWithLifecycle()
    val toast = rememberToast()
    var picking by remember { mutableStateOf<ProductCardDto?>(null) }

    MbScreen(topBar = { MbTopBar(stringResource(R.string.sevimlilar), onBack = onBack) }) { padding ->
        Box(
            Modifier
                .fillMaxSize()
                .padding(padding)
        ) {
            when {
                loading -> MbLoading()
                items.isEmpty() -> MbEmptyState(
                    glyph = "heart",
                    title = stringResource(R.string.sevimlilar_bosh),
                    message = stringResource(R.string.yoqqan_tovarlarni_belgilab_qoying_narx),
                    actionLabel = stringResource(R.string.xaridni_boshlash),
                    onAction = onStartShopping,
                )

                else -> LazyVerticalGrid(
                    columns = GridCells.Fixed(2),
                    // The home page's edge and the home page's gap, so a card
                    // here is the same card at the same width as a card there.
                    contentPadding = PaddingValues(MbTheme.dimens.homeEdge),
                    horizontalArrangement = Arrangement.spacedBy(MbTheme.dimens.cardGap),
                    verticalArrangement = Arrangement.spacedBy(14.dp),
                ) {
                    items(items, key = { it.id }) { product ->
                        MbProductTile(
                            title = product.title,
                            price = product.price,
                            oldPrice = product.oldPrice,
                            discountPercent = product.discountPercent,
                            imageUrl = product.imageUrl,
                            images = product.images,
                            isFavorite = true,
                            inStock = product.inStock,
                            stockLeft = product.stockLeft,
                            onClick = { onOpenProduct(product.id) },
                            onToggleFavorite = { viewModel.remove(product.id) },
                            // The sheet, as everywhere else. This was the
                            // worst of the direct-add screens: a favourite with
                            // sizes went into the basket with no size chosen at
                            // all, because nothing here ever opened a picker.
                            onAddToCart = { if (picking == null) picking = product },
                        )
                    }
                }
            }
            MbToastHost(toast, Modifier.align(Alignment.BottomCenter).padding(bottom = 24.dp))
        }
    }

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
