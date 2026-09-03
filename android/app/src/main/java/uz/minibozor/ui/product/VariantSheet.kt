package uz.minibozor.ui.product

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import uz.minibozor.R
import uz.minibozor.core.design.MbText
import uz.minibozor.core.design.MbTheme
import uz.minibozor.core.design.mbClickable
import uz.minibozor.core.design.mbTap
import uz.minibozor.core.design.component.MbLoading
import uz.minibozor.core.design.component.MbPrimaryButton
import uz.minibozor.core.design.component.MbProductImage
import uz.minibozor.core.design.component.MbQuantityStepper
import uz.minibozor.core.design.component.MbStatusPill
import uz.minibozor.core.design.icon.MbIcon
import uz.minibozor.core.util.discountPill
import uz.minibozor.core.util.grouped
import uz.minibozor.core.util.sum
import uz.minibozor.core.util.toColor
import uz.minibozor.data.remote.dto.ProductCardDto
import uz.minibozor.data.remote.dto.VariantDto

/**
 * The picker a tile opens when a product comes in more than one size or
 * colour, instead of guessing one and adding it.
 *
 * The summary at the top is drawn from the tile's own data so the sheet has
 * something to show the moment it starts sliding up; the variants fill in
 * underneath when the request lands.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun VariantSheet(
    card: ProductCardDto,
    onDismiss: () -> Unit,
    onOpenCart: () -> Unit,
    viewModel: VariantSheetViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)

    LaunchedEffect(card.id) { viewModel.load(card.id) }

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = sheetState,
        containerColor = MbTheme.colors.surface,
        shape = MbTheme.shapes.sheet,
        dragHandle = null,
    ) {
        Column(Modifier.fillMaxWidth()) {
            Handle()

            Row(
                Modifier
                    .fillMaxWidth()
                    .padding(start = 20.dp, end = 12.dp, bottom = 4.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                MbText(
                    stringResource(R.string.xususiyatlarni_tanlang),
                    MbTheme.type.title2,
                    modifier = Modifier.weight(1f),
                )
                Box(
                    Modifier
                        .size(32.dp)
                        .clip(CircleShape)
                        .background(MbTheme.colors.fill)
                        .mbTap(onClick = onDismiss),
                    contentAlignment = Alignment.Center,
                ) {
                    MbIcon("close", size = 14.dp, tint = MbTheme.colors.inkSoft)
                }
            }

            Column(
                Modifier
                    .heightIn(max = 460.dp)
                    .verticalScroll(rememberScrollState())
                    .padding(horizontal = 20.dp),
            ) {
                Spacer(Modifier.height(8.dp))
                Summary(card)

                if (state.loading) {
                    Box(Modifier.fillMaxWidth().height(140.dp)) { MbLoading() }
                } else {
                    if (state.colors.isNotEmpty()) {
                        Spacer(Modifier.height(20.dp))
                        Label(
                            stringResource(R.string.rang),
                            state.selectedColor?.label.orEmpty(),
                        )
                        Spacer(Modifier.height(10.dp))
                        ColorRow(state.colors, state.colorId, viewModel::selectColor)
                    }
                    if (state.sizes.isNotEmpty()) {
                        Spacer(Modifier.height(20.dp))
                        Label(
                            stringResource(R.string.olcham),
                            state.selectedSize?.label.orEmpty(),
                        )
                        Spacer(Modifier.height(10.dp))
                        SizeRow(state.sizes, state.sizeId, viewModel::selectSize)
                    }
                }

                if (state.error != null) {
                    Spacer(Modifier.height(12.dp))
                    MbText(state.error!!, MbTheme.type.caption, MbTheme.colors.danger)
                }
                Spacer(Modifier.height(16.dp))
            }

            BottomBar(
                state = state,
                onAdd = viewModel::addToCart,
                onQuantity = viewModel::setQuantity,
                onOpenCart = onOpenCart,
            )
        }
    }
}

@Composable
private fun Handle() {
    Box(Modifier.fillMaxWidth().padding(vertical = 10.dp), contentAlignment = Alignment.Center) {
        Box(
            Modifier
                .size(width = 38.dp, height = 4.dp)
                .clip(MbTheme.shapes.chip)
                .background(MbTheme.colors.hairline)
        )
    }
}

/** Drawn from the tile's data, so it is on screen before the request lands. */
@Composable
private fun Summary(card: ProductCardDto) {
    Row(
        Modifier
            .fillMaxWidth()
            .clip(MbTheme.shapes.tile)
            .border(1.dp, MbTheme.colors.border, MbTheme.shapes.tile)
            .padding(10.dp),
    ) {
        MbProductImage(
            card.imageUrl,
            modifier = Modifier.size(84.dp),
            shape = MbTheme.shapes.tileSmall,
        )
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            MbText(card.title, MbTheme.type.bodySmall, maxLines = 2)
            Spacer(Modifier.height(6.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                MbText(
                    card.price.sum(),
                    MbTheme.type.title3,
                )
                if (card.discountPercent != null) {
                    Spacer(Modifier.width(8.dp))
                    MbText(
                        card.discountPercent.discountPill(),
                        MbTheme.type.caption,
                        MbTheme.colors.danger,
                    )
                }
            }
            if (card.oldPrice != null) {
                MbText(
                    card.oldPrice.grouped(),
                    MbTheme.type.meta.copy(textDecoration = TextDecoration.LineThrough),
                    MbTheme.colors.textQuaternary,
                )
            }
        }
    }
}

@Composable
private fun Label(name: String, value: String) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        MbText("$name:", MbTheme.type.bodySmall, MbTheme.colors.textSecondary)
        Spacer(Modifier.width(6.dp))
        MbText(value, MbTheme.type.bodySmall.copy(fontWeight = FontWeight.Bold))
    }
}

/**
 * The colours, as photographs where the shop supplied one.
 *
 * The same treatment as the product page's own picker: nobody knows what
 * "#2F4B8F" looks like on a suede shoe, and the sheet is where the choice is
 * actually made. A colour with no photograph keeps its swatch.
 */
@Composable
private fun ColorRow(colors: List<VariantDto>, selectedId: Int?, onSelect: (Int) -> Unit) {
    Row(
        Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        colors.forEach { color ->
            val selected = color.id == selectedId
            Box(
                Modifier
                    .size(62.dp)
                    .clip(MbTheme.shapes.tile)
                    .border(
                        width = if (selected) 2.dp else 1.dp,
                        color = if (selected) MbTheme.colors.ink else MbTheme.colors.border,
                        shape = MbTheme.shapes.tile,
                    )
                    .mbClickable(MbTheme.shapes.tile, enabled = color.inStock) {
                        onSelect(color.id)
                    }
                    .padding(if (selected) 4.dp else 3.dp),
            ) {
                if (color.imageUrl != null) {
                    MbProductImage(
                        color.imageUrl,
                        modifier = Modifier.fillMaxSize(),
                        shape = MbTheme.shapes.tileSmall,
                    )
                } else {
                    Box(
                        Modifier
                            .fillMaxSize()
                            .clip(MbTheme.shapes.tileSmall)
                            .background(color.value.toColor(MbTheme.colors.fill))
                    )
                }
            }
        }
    }
}

@Composable
private fun SizeRow(sizes: List<VariantDto>, selectedId: Int?, onSelect: (Int) -> Unit) {
    Row(
        Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        sizes.forEach { size ->
            val selected = size.id == selectedId
            Box(
                Modifier
                    .clip(MbTheme.shapes.field)
                    .background(
                        if (selected) MbTheme.colors.inverse else MbTheme.colors.surface
                    )
                    .border(
                        width = if (selected) 1.6.dp else 1.dp,
                        color = if (selected) MbTheme.colors.inverse else MbTheme.colors.border,
                        shape = MbTheme.shapes.field,
                    )
                    .mbClickable(MbTheme.shapes.field, enabled = size.inStock) {
                        onSelect(size.id)
                    }
                    .padding(horizontal = 18.dp, vertical = 12.dp),
            ) {
                MbText(
                    size.label,
                    MbTheme.type.label.copy(
                        // Out of stock reads as struck through, the way the
                        // design marks a size it cannot sell.
                        textDecoration =
                            if (size.inStock) null else TextDecoration.LineThrough,
                    ),
                    when {
                        !size.inStock -> MbTheme.colors.disabled
                        selected -> MbTheme.colors.onInverse
                        else -> MbTheme.colors.ink
                    },
                )
            }
        }
    }
}

/** "Savatga" before the line exists, a stepper and "O'tish" once it does. */
@Composable
private fun BottomBar(
    state: VariantSheetState,
    onAdd: () -> Unit,
    onQuantity: (Int) -> Unit,
    onOpenCart: () -> Unit,
) {
    Column(
        Modifier
            .fillMaxWidth()
            .background(MbTheme.colors.surfaceAlt)
            .padding(horizontal = 20.dp, vertical = 14.dp),
    ) {
        if (state.cartItemId == null) {
            MbPrimaryButton(
                text = stringResource(R.string.savatga),
                onClick = onAdd,
                enabled = state.ready && !state.busy,
                loading = state.busy,
            )
        } else {
            Row(verticalAlignment = Alignment.CenterVertically) {
                MbQuantityStepper(
                    quantity = state.quantity,
                    onChange = onQuantity,
                    min = 0,
                    // Where the shelf ends, as everywhere else the count can be
                    // raised.
                    max = (state.product?.stockLeft ?: 1).coerceAtLeast(1),
                    // Matches the button beside it, so the two sit as one bar.
                    size = MbTheme.dimens.buttonHeight,
                )
                Spacer(Modifier.width(12.dp))
                MbPrimaryButton(
                    text = stringResource(R.string.otish),
                    onClick = onOpenCart,
                    leadingGlyph = "cart",
                    modifier = Modifier.weight(1f),
                )
            }
        }
    }
}
