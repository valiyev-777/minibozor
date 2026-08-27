package uz.minibozor.ui.catalog

import androidx.compose.ui.res.pluralStringResource
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import uz.minibozor.R
import uz.minibozor.core.design.MbText
import uz.minibozor.core.design.MbTheme
import uz.minibozor.core.design.component.MbTabHeader
import uz.minibozor.core.design.component.MbCard
import uz.minibozor.core.design.component.MbDivider
import uz.minibozor.core.design.component.MbListRow
import uz.minibozor.core.design.component.MbProductImage
import uz.minibozor.core.design.component.MbScreen
import uz.minibozor.core.design.component.MbSearchPill
import uz.minibozor.core.design.component.MbTabBarSpacer
import uz.minibozor.core.design.component.MbTopBar
import uz.minibozor.core.util.grouped
import uz.minibozor.data.remote.dto.CategoryDto
import uz.minibozor.ui.common.UiStateContent
import uz.minibozor.ui.common.dataOrNull

/** Screen 10 — Katalog. */
@Composable
fun CatalogScreen(
    onOpenSearch: () -> Unit,
    onOpenCategory: (CategoryDto) -> Unit,
    viewModel: CatalogViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()

    MbScreen { padding ->
        Column(
            Modifier
                .fillMaxSize()
                .padding(padding)
        ) {
            MbTabHeader(
                stringResource(R.string.katalog),
                below = {
                    MbSearchPill(stringResource(R.string.turkum_yoki_mahsulot_qidirish), onOpenSearch)
                },
            )

            UiStateContent(state, viewModel::load) { categories ->
                LazyColumn(
                    Modifier.fillMaxSize(),
                    contentPadding = androidx.compose.foundation.layout.PaddingValues(12.dp),
                ) {
                    item {
                        MbCard(padding = 4.dp) {
                            categories.forEachIndexed { index, category ->
                                MbListRow(
                                    label = category.name,
                                    glyph = category.icon,
                                    imageUrl = category.imageUrl,
                                    subtitle = category.subtitle.ifBlank { null },
                                    meta = if (category.productCount > 0) {
                                        pluralStringResource(
                    R.plurals.n_products,
                    category.productCount,
                    category.productCount.grouped(),
                )
                                    } else null,
                                    onClick = { onOpenCategory(category) },
                                    contentPadding = 12.dp,
                                )
                                if (index != categories.lastIndex) MbDivider(inset = 62.dp)
                            }
                        }
                    }
                    item { MbTabBarSpacer() }
                }
            }
        }
    }
}

/** Screen 11 — Subkategoriya. */
@Composable
fun SubcategoryScreen(
    slug: String,
    onBack: () -> Unit,
    onOpenListing: (slug: String, title: String) -> Unit,
    viewModel: SubcategoryViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    LaunchedEffect(slug) { viewModel.load(slug) }

    MbScreen(
        topBar = {
            MbTopBar(
                title = state.dataOrNull?.first?.name ?: stringResource(R.string.turkum),
                onBack = onBack,
            )
        },
    ) { padding ->
        UiStateContent(state, viewModel::retry, Modifier.padding(padding)) { (parent, children) ->
            LazyColumn(
                Modifier.fillMaxSize(),
                contentPadding = androidx.compose.foundation.layout.PaddingValues(12.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                item {
                    MbCard(padding = 8.dp) {
                        MbListRow(
                            label = stringResource(R.string.barcha_tovarlar),
                            glyph = parent.icon,
                            meta = pluralStringResource(
                    R.plurals.n_products,
                    parent.productCount,
                    parent.productCount.grouped(),
                ),
                            onClick = { onOpenListing(parent.slug, parent.name) },
                            contentPadding = 8.dp,
                        )
                    }
                }
                items(children, key = { it.id }) { child ->
                    MbCard(padding = 10.dp) {
                        Row(
                            Modifier
                                .fillMaxWidth()
                                .clickable { onOpenListing(child.slug, child.name) },
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(14.dp),
                        ) {
                            MbProductImage(
                                child.imageUrl,
                                modifier = Modifier.size(60.dp),
                                shape = MbTheme.shapes.tileSmall,
                            )
                            Column(Modifier.weight(1f)) {
                                MbText(
                                    child.name,
                                    MbTheme.type.body.copy(
                                        fontWeight = androidx.compose.ui.text.font.FontWeight.Bold),
                                )
                                MbText(
                                    pluralStringResource(
                    R.plurals.n_products,
                    child.productCount,
                    child.productCount.grouped(),
                ),
                                    MbTheme.type.meta,
                                    MbTheme.colors.icon,
                                )
                            }
                            MbText("›", MbTheme.type.title3, MbTheme.colors.hairlineStrong)
                        }
                    }
                }
            }
        }
    }
}
