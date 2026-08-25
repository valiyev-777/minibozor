package uz.minibozor.ui.catalog

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
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
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
    viewModel: ListingViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val gridState = rememberLazyGridState()
    val toast = rememberToast()
    var showFilters by remember { mutableStateOf(false) }

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
                title = title.ifBlank { query.orEmpty().ifBlank { "Tovarlar" } },
                subtitle = if (state.total > 0) "${state.total.grouped()} ta topildi" else null,
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
                                title = "Hech narsa topilmadi",
                                message = "Filtrlarni yumshatib yoki boshqa so'z bilan qidirib ko'ring.",
                                actionLabel = "Filtrlarni tozalash",
                                onAction = { viewModel.apply(state.query.cleared()) },
                            )
                        } else {
                            // The category exists but has no stock yet.
                            MbEmptyState(
                                glyph = "box",
                                title = "Tovarlar tez orada qo'shiladi",
                                message = "Bu turkumni to'ldirib borayapmiz. " +
                                    "Tez kunda birinchi tovarlar paydo bo'ladi.",
                                actionLabel = "Boshqa turkumlarni ko'rish",
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
                                badge = product.badge,
                                isFavorite = product.isFavorite,
                                onClick = { onOpenProduct(product.id) },
                                onToggleFavorite = { viewModel.toggleFavorite(product) },
                                onAddToCart = {
                                    viewModel.addToCart(product.id) { toast.value = it }
                                },
                            )
                        }
                    }
                }
                MbToastHost(toast, Modifier.align(Alignment.BottomCenter).padding(bottom = 24.dp))
            }
        }
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
                if (total > 0) "${total.grouped()} ta tovar" else "Tovarlar",
                MbTheme.type.label,
                MbTheme.colors.ink,
            )
            MbText(sortLabel, MbTheme.type.meta, MbTheme.colors.icon, maxLines = 1)
        }
        Row(
            Modifier
                .mbClickable(MbTheme.shapes.chip, onClick = onOpenFilters)
                .background(if (filterCount > 0) MbTheme.colors.ink else MbTheme.colors.fill)
                .padding(horizontal = 14.dp, vertical = 9.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            MbIcon(
                "gear",
                size = 14.dp,
                tint = if (filterCount > 0) Color.White else MbTheme.colors.ink,
            )
            MbText(
                if (filterCount > 0) "Filtr · $filterCount" else "Filtr",
                MbTheme.type.caption,
                if (filterCount > 0) Color.White else MbTheme.colors.ink,
            )
        }
    }
}

/** "Ommabop", "Avval arzoni" … shown as a subtitle instead of a chip row. */
private fun sortLabel(sorts: List<Map<String, String>>?, current: String): String =
    sorts?.firstOrNull { it["key"] == current }?.get("label") ?: "Saralash"
