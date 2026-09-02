package uz.minibozor.ui.search

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import uz.minibozor.R
import uz.minibozor.core.design.MbText
import uz.minibozor.core.design.MbTheme
import uz.minibozor.core.design.component.MbChip
import uz.minibozor.core.design.component.MbProductImage
import uz.minibozor.core.design.component.MbScreen
import uz.minibozor.core.design.component.MbSearchField
import uz.minibozor.core.design.component.SectionHeader
import uz.minibozor.core.design.icon.MbIcon
import uz.minibozor.core.util.sum

/**
 * Screen 08. Recent and popular queries until two characters are typed, then
 * live product suggestions.
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun SearchScreen(
    onBack: () -> Unit,
    onSubmit: (String) -> Unit,
    onOpenProduct: (Int) -> Unit,
    viewModel: SearchViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()

    fun submit(query: String) {
        if (query.isBlank()) return
        viewModel.remember(query)
        onSubmit(query)
    }

    MbScreen(background = MbTheme.colors.surface) { padding ->
        Column(Modifier.fillMaxSize()) {
            Row(
                Modifier
                    .fillMaxWidth()
                    .background(MbTheme.colors.surface)
                    .windowInsetsPadding(WindowInsets.statusBars)
                    .padding(horizontal = 16.dp, vertical = 10.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                MbSearchField(
                    value = state.query,
                    onValueChange = viewModel::onQueryChange,
                    onSubmit = { submit(state.query) },
                    modifier = Modifier.weight(1f),
                )
                MbText(
                    stringResource(R.string.bekor),
                    MbTheme.type.label,
                    MbTheme.colors.accent,
                    // A pill of tap area around the word, so the press reads
                    // as a rounded highlight rather than a rectangle the size
                    // of the text.
                    modifier = Modifier
                        .clip(MbTheme.shapes.chip)
                        .clickable(onClick = onBack)
                        .padding(horizontal = 8.dp, vertical = 6.dp),
                )
            }

            if (state.suggestions.isNotEmpty()) {
                LazyColumn(Modifier.padding(horizontal = 20.dp)) {
                    items(state.suggestions, key = { it.productId }) { item ->
                        Row(
                            Modifier
                                .fillMaxWidth()
                                .clickable { onOpenProduct(item.productId) }
                                .padding(vertical = 10.dp),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(12.dp),
                        ) {
                            MbProductImage(
                                item.imageUrl,
                                modifier = Modifier.size(44.dp),
                                shape = MbTheme.shapes.field,
                            )
                            Column(Modifier.weight(1f)) {
                                MbText(item.title, MbTheme.type.bodySmall, maxLines = 1)
                                MbText(item.price.sum(), MbTheme.type.meta, MbTheme.colors.icon)
                            }
                            MbIcon("search", size = 14.dp, tint = MbTheme.colors.hairlineStrong)
                        }
                    }
                }
            } else {
                Column(
                    Modifier
                        .fillMaxSize()
                        .padding(padding)
                        .padding(horizontal = 20.dp),
                ) {
                    if (state.recent.isNotEmpty()) {
                        Spacer(Modifier.height(18.dp))
                        SectionHeader(
                            title = stringResource(R.string.oxirgi_qidiruvlar),
                            actionLabel = stringResource(R.string.tozalash),
                            onAction = viewModel::clearHistory,
                        )
                        Spacer(Modifier.height(12.dp))
                        state.recent.forEach { query ->
                            Row(
                                Modifier
                                    .fillMaxWidth()
                                    .clickable { submit(query) }
                                    .padding(vertical = 11.dp),
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(12.dp),
                            ) {
                                MbIcon("clock", size = 16.dp, tint = MbTheme.colors.icon)
                                MbText(query, MbTheme.type.bodySmall, modifier = Modifier.weight(1f))
                                MbText("↖", MbTheme.type.caption, MbTheme.colors.hairlineStrong)
                            }
                        }
                    }

                    if (state.popular.isNotEmpty()) {
                        Spacer(Modifier.height(22.dp))
                        SectionHeader(title = stringResource(R.string.ommabop_sorovlar))
                        Spacer(Modifier.height(12.dp))
                        FlowRow(
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                            verticalArrangement = Arrangement.spacedBy(8.dp),
                        ) {
                            state.popular.forEach { query ->
                                MbChip(query, selected = false, onClick = { submit(query) })
                            }
                        }
                    }
                }
            }
        }
    }
}
