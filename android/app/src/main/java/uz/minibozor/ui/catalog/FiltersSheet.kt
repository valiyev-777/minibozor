package uz.minibozor.ui.catalog

import androidx.compose.foundation.clickable
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
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import uz.minibozor.core.design.MbText
import uz.minibozor.core.design.MbTheme
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

    Column(
        Modifier
            .fillMaxWidth()
            .heightIn(max = 640.dp)
    ) {
        Row(
            Modifier
                .fillMaxWidth()
                .padding(horizontal = 20.dp, vertical = 6.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            MbText("Filtrlar", MbTheme.type.title2)
            Spacer(Modifier.weight(1f))
            MbText(
                "Tozalash",
                MbTheme.type.label,
                MbTheme.colors.accent,
                modifier = Modifier
                    .clickable {
                        draft = draft.cleared()
                        minPrice = ""
                        maxPrice = ""
                    }
                    .padding(8.dp),
            )
        }
        MbDivider()

        Column(
            Modifier
                .weight(1f, fill = false)
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 20.dp),
        ) {
            Spacer(Modifier.height(16.dp))
            SectionHeader("Narx", "so'm")
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
                SectionHeader("Brend")
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
                SectionHeader("O'lcham")
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
                SectionHeader("Reyting")
                Spacer(Modifier.height(10.dp))
                FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    val options = listOf(4.5 to "4.5 ★ dan yuqori", 4.0 to "4.0 ★ dan yuqori")
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

            if (!filters?.flags.isNullOrEmpty()) {
                Spacer(Modifier.height(22.dp))
                SectionHeader("Qo'shimcha")
                Spacer(Modifier.height(4.dp))
                filters!!.flags.forEach { flag ->
                    MbCheckRow(
                        label = flag.label,
                        subtitle = flag.subtitle.ifBlank { null },
                        checked = draft.flags[flag.key] == true,
                        onToggle = { draft = draft.toggleFlag(flag.key) },
                        count = flag.count.takeIf { it > 0 }?.toString(),
                    )
                }
            }

            Spacer(Modifier.height(20.dp))
        }

        MbDivider()
        Column(Modifier.padding(20.dp)) {
            MbPrimaryButton(
                text = if (resultCount > 0) {
                    "Ko'rsatish · ${resultCount.grouped()} ta"
                } else "Qo'llash",
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
