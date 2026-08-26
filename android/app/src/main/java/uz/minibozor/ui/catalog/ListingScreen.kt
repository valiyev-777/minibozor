package uz.minibozor.ui.catalog

import androidx.compose.ui.res.pluralStringResource
import uz.minibozor.ui.product.VariantSheet
import uz.minibozor.data.remote.dto.ProductCardDto
import uz.minibozor.core.util.AppStrings
import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
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
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.lazy.grid.rememberLazyGridState
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import uz.minibozor.R
import uz.minibozor.core.design.MbText
import uz.minibozor.core.design.MbTheme
import uz.minibozor.core.design.mbClickable
import uz.minibozor.core.design.component.MbChip
import uz.minibozor.core.design.component.MbEmptyState
import uz.minibozor.core.design.component.MbErrorState
import uz.minibozor.core.design.component.MbLoading
import uz.minibozor.core.design.component.MbProductTile
import uz.minibozor.core.design.component.MbScreen
import uz.minibozor.core.design.component.MbTopBar
import uz.minibozor.core.design.icon.MbIcon
import uz.minibozor.core.util.grouped
import uz.minibozor.ui.common.MbToastHost
import uz.minibozor.ui.common.rememberToast

/**
 * Screens 09 and 12. The toolbar carries the result count, the sort chips and
 * the filter button; the filter sheet (screen 13) opens over it.
 */
@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun ListingScreen(
    title: String,
    category: String?,
    query: String?,
    onBack: () -> Unit,
    onOpenProduct: (Int) -> Unit,
    onOpenCart: () -> Unit,
    viewModel: ListingViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val gridState = rememberLazyGridState()
    val toast = rememberToast()
    var showFilters by remember { mutableStateOf(false) }
    var picking by remember { mutableStateOf<ProductCardDto?>(null) }

    LaunchedEffect(category, query) { viewModel.start(category, query) }

    val atEnd by remember {
        derivedStateOf {
            val last = gridState.layoutInfo.visibleItemsInfo.lastOrNull()?.index ?: 0
            last >= state.items.lastIndex - 4
        }
    }
    LaunchedEffect(atEnd) { if (atEnd) viewModel.loadMore() }

    MbScreen(
        topBar = {
            MbTopBar(
                title = title.ifBlank { query.orEmpty().ifBlank { stringResource(R.string.tovarlar) } },
                subtitle = if (state.total > 0) pluralStringResource(
                    R.plurals.n_found,
                    state.total,
                    state.total.grouped(),
                ) else null,
                onBack = onBack,
            )
        },
    ) { padding ->
        Column(
            Modifier
                .fillMaxSize()
                .padding(padding)
        ) {
            Toolbar(
                total = state.total,
                sortLabel = sortLabel(state.filters?.sorts, state.query.sort),
                filterCount = state.query.activeFilterCount,
                onOpenFilters = { showFilters = true },
            )

            Box(Modifier.fillMaxSize()) {
                when {
                    state.loading -> MbLoading()
                    state.error != null -> MbErrorState(state.error!!, viewModel::reload)
                    state.items.isEmpty() -> {
                        val filtered = state.query.activeFilterCount > 0 ||
                            !state.query.text.isNullOrBlank()
                        if (filtered) {
                            MbEmptyState(
                                glyph = "search",
                                title = stringResource(R.string.hech_narsa_topilmadi),
                                message = stringResource(R.string.filtrlarni_yumshatib_yoki_boshqa_soz_bilan),
                                actionLabel = stringResource(R.string.filtrlarni_tozalash),
                                onAction = { viewModel.apply(state.query.cleared()) },
                            )
                        } else {
                            // The category exists but has no stock yet.
                            MbEmptyState(
                                glyph = "box",
                                title = stringResource(R.string.tovarlar_tez_orada_qoshiladi),
                                message = stringResource(R.string.bu_turkumni_toldirib_borayapmiz_tez_kunda),
                                actionLabel = stringResource(R.string.boshqa_turkumlarni_korish),
                                onAction = onBack,
                            )
                        }
                    }
                    else -> LazyVerticalGrid(
                        columns = GridCells.Fixed(2),
                        state = gridState,
                        contentPadding = PaddingValues(14.dp),
                        horizontalArrangement = Arrangement.spacedBy(16.dp),
                        verticalArrangement = Arrangement.spacedBy(18.dp),
                    ) {
                        items(state.items, key = { it.id }) { product ->
                            MbProductTile(
                                title = product.title,
                                price = product.price,
                                oldPrice = product.oldPrice,
                                discountPercent = product.discountPercent,
                                imageUrl = product.imageUrl,
                                rating = product.rating,
                                reviewsCount = product.reviewsCount,
                                isFavorite = product.isFavorite,
                                onClick = { onOpenProduct(product.id) },
                                onToggleFavorite = { viewModel.toggleFavorite(product) },
                                onAddToCart = {
                                    if (product.hasVariants) {
                                        picking = product
                                    } else {
                                        viewModel.addToCart(product.id) { toast.value = it }
                                    }
                                },
                            )
                        }
                    }
                }
                MbToastHost(toast, Modifier.align(Alignment.BottomCenter).padding(bottom = 24.dp))
            }
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

    if (showFilters) {
        ModalBottomSheet(
            onDismissRequest = { showFilters = false },
            sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
            containerColor = MbTheme.colors.surface,
            shape = MbTheme.shapes.sheet,
        ) {
            FiltersSheet(
                filters = state.filters,
                initial = state.query,
                resultCount = state.total,
                onApply = {
                    viewModel.apply(it)
                    showFilters = false
                },
                onDismiss = { showFilters = false },
            )
        }
    }
}

@Composable
private fun Toolbar(
    total: Int,
    sortLabel: String,
    filterCount: Int,
    onOpenFilters: () -> Unit,
) {
    Row(
        Modifier
            .fillMaxWidth()
            .background(MbTheme.colors.surface)
            .padding(horizontal = 16.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            MbText(
                if (total > 0) pluralStringResource(R.plurals.n_products, total, total.grouped()) else stringResource(R.string.tovarlar),
                MbTheme.type.label,
                MbTheme.colors.ink,
            )
            MbText(sortLabel, MbTheme.type.meta, MbTheme.colors.icon, maxLines = 1)
        }
        Row(
            Modifier
                .mbClickable(MbTheme.shapes.chip, onClick = onOpenFilters)
                .background(if (filterCount > 0) MbTheme.colors.inverse else MbTheme.colors.fill)
                .padding(horizontal = 14.dp, vertical = 9.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            MbIcon(
                "gear",
                size = 14.dp,
                tint = if (filterCount > 0) MbTheme.colors.onInverse else MbTheme.colors.ink,
            )
            MbText(
                if (filterCount > 0) stringResource(R.string.filtr_n, filterCount) else stringResource(R.string.filtr),
                MbTheme.type.caption,
                if (filterCount > 0) MbTheme.colors.onInverse else MbTheme.colors.ink,
            )
        }
    }
}

/** "Ommabop", "Avval arzoni" … shown as a subtitle instead of a chip row. */
private fun sortLabel(sorts: List<Map<String, String>>?, current: String): String =
    sorts?.firstOrNull { it["key"] == current }?.get("label")
        ?: AppStrings[R.string.saralash]
