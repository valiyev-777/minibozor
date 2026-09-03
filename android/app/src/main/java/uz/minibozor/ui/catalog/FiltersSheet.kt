package uz.minibozor.ui.catalog

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import uz.minibozor.R
import uz.minibozor.core.design.MbText
import uz.minibozor.core.design.MbTheme
import uz.minibozor.core.design.mbClickable
import uz.minibozor.core.design.component.MbCheckRow
import uz.minibozor.core.design.component.MbChip
import uz.minibozor.core.design.component.MbDivider
import uz.minibozor.core.design.component.MbPrimaryButton
import uz.minibozor.core.design.component.MbSizeChip
import uz.minibozor.core.design.component.MbTextField
import uz.minibozor.core.design.component.SectionHeader
import uz.minibozor.core.util.grouped
import uz.minibozor.data.remote.dto.FiltersDto

/**
 * Screen 13. Edits a draft copy of the query so "Tozalash" and dismissing both
 * leave the listing untouched — only "Qo'llash" commits.
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun FiltersSheet(
    filters: FiltersDto?,
    initial: ProductQuery,
    resultCount: Int,
    onApply: (ProductQuery) -> Unit,
    onDismiss: () -> Unit,
) {
    var draft by remember { mutableStateOf(initial) }
    var minPrice by remember { mutableStateOf(initial.minPrice?.toString().orEmpty()) }
    var maxPrice by remember { mutableStateOf(initial.maxPrice?.toString().orEmpty()) }

    // Two thirds of the screen rather than a fixed 640 points. On a tall
    // phone that fixed number was most of the display: the sheet opened
    // almost at the status bar and read as a page that had replaced the
    // listing rather than as a panel over it, with nothing of the grid left
    // behind it to dismiss back to. A share of the screen keeps the same
    // proportion on every device, and the sections inside still scroll.
    val screenHeight = LocalConfiguration.current.screenHeightDp.dp
    Column(
        Modifier
            .fillMaxWidth()
            .heightIn(max = (screenHeight * 0.66f).coerceIn(420.dp, 640.dp))
    ) {
        Row(
            Modifier
                .fillMaxWidth()
                .padding(horizontal = 20.dp, vertical = 6.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            MbText(stringResource(R.string.filtrlar), MbTheme.type.title2)
            Spacer(Modifier.weight(1f))
            MbText(
                stringResource(R.string.tozalash),
                MbTheme.type.label,
                MbTheme.colors.accent,
                modifier = Modifier
                    .mbClickable(MbTheme.shapes.chip) {
                        draft = draft.cleared()
                        minPrice = ""
                        maxPrice = ""
                    }
                    // Inside the click, not outside it: the padding is the
                    // difference between a word-sized tap target and a
                    // finger-sized one, and the ripple should cover both.
                    .padding(horizontal = 10.dp, vertical = 8.dp),
            )
        }
        MbDivider()

        Column(
            Modifier
                .weight(1f, fill = false)
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 20.dp),
        ) {
            if (!filters?.sorts.isNullOrEmpty()) {
                Spacer(Modifier.height(16.dp))
                SectionHeader(stringResource(R.string.saralash))
                Spacer(Modifier.height(10.dp))
                FlowRow(
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    filters!!.sorts.forEach { option ->
                        val key = option["key"].orEmpty()
                        MbChip(
                            label = option["label"].orEmpty(),
                            selected = draft.sort == key,
                            onClick = { draft = draft.copy(sort = key) },
                        )
                    }
                }
            }

            Spacer(Modifier.height(22.dp))
            SectionHeader(stringResource(R.string.narx), stringResource(R.string.som))
            Spacer(Modifier.height(10.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                MbTextField(
                    value = minPrice,
                    onValueChange = { minPrice = it.filter(Char::isDigit) },
                    placeholder = filters?.priceMin?.grouped() ?: "0",
                    keyboardType = KeyboardType.Number,
                    modifier = Modifier.weight(1f),
                )
                MbTextField(
                    value = maxPrice,
                    onValueChange = { maxPrice = it.filter(Char::isDigit) },
                    placeholder = filters?.priceMax?.grouped() ?: "∞",
                    keyboardType = KeyboardType.Number,
                    modifier = Modifier.weight(1f),
                )
            }

            if (!filters?.brands.isNullOrEmpty()) {
                Spacer(Modifier.height(22.dp))
                SectionHeader(stringResource(R.string.brend))
                Spacer(Modifier.height(4.dp))
                filters!!.brands.forEach { brand ->
                    MbCheckRow(
                        label = brand.name,
                        checked = brand.slug in draft.brands,
                        onToggle = { draft = draft.toggleBrand(brand.slug) },
                        count = brand.productCount.takeIf { it > 0 }?.toString(),
                    )
                }
            }

            if (!filters?.sizes.isNullOrEmpty()) {
                Spacer(Modifier.height(22.dp))
                SectionHeader(stringResource(R.string.olcham))
                Spacer(Modifier.height(10.dp))
                FlowRow(
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    filters!!.sizes.forEach { size ->
                        MbSizeChip(
                            label = size,
                            selected = size in draft.sizes,
                            onClick = { draft = draft.toggleSize(size) },
                        )
                    }
                }
            }

            if (!filters?.ratings.isNullOrEmpty()) {
                Spacer(Modifier.height(22.dp))
                SectionHeader(stringResource(R.string.reyting))
                Spacer(Modifier.height(10.dp))
                FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    val options = listOf(4.5 to stringResource(R.string.rating_4_5_dan_yuqori), 4.0 to stringResource(R.string.rating_4_0_dan_yuqori))
                    options.forEach { (value, label) ->
                        MbChip(
                            label = label,
                            selected = draft.minRating == value,
                            onClick = {
                                draft = draft.copy(
                                    minRating = if (draft.minRating == value) null else value
                                )
                            },
                        )
                    }
                }
            }

            Spacer(Modifier.height(22.dp))
            SectionHeader(stringResource(R.string.qoshimcha))
            Spacer(Modifier.height(4.dp))
            filters?.flags.orEmpty().forEach { flag ->
                MbCheckRow(
                    label = flag.label,
                    subtitle = flag.subtitle.ifBlank { null },
                    checked = draft.flags[flag.key] == true,
                    onToggle = { draft = draft.toggleFlag(flag.key) },
                    count = flag.count.takeIf { it > 0 }?.toString(),
                )
            }
            // Last in the section, and the only row here that is about the
            // listing rather than about the products: everything else narrows
            // what is shown, and this one widens it.
            MbCheckRow(
                label = stringResource(R.string.tugaganlarni_korsatish),
                subtitle = stringResource(R.string.tugaganlar_odatda_royxatda_korinmaydi),
                checked = draft.showSoldOut,
                onToggle = { draft = draft.copy(showSoldOut = !draft.showSoldOut) },
            )

            Spacer(Modifier.height(20.dp))
        }

        MbDivider()
        Column(Modifier.padding(20.dp)) {
            MbPrimaryButton(
                text = if (resultCount > 0) {
                    stringResource(R.string.korsatish_n, resultCount.grouped())
                } else stringResource(R.string.qollash),
                onClick = {
                    onApply(
                        draft.copy(
                            minPrice = minPrice.toIntOrNull(),
                            maxPrice = maxPrice.toIntOrNull(),
                        )
                    )
                },
            )
        }
    }
}
