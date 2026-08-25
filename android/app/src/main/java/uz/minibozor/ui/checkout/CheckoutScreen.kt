package uz.minibozor.ui.checkout

import androidx.compose.ui.res.pluralStringResource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import uz.minibozor.R
import uz.minibozor.core.design.MbText
import uz.minibozor.core.design.MbTheme
import uz.minibozor.core.design.component.MbBottomBar
import uz.minibozor.core.design.component.MbCard
import uz.minibozor.core.design.component.MbDivider
import uz.minibozor.core.design.component.MbLineItem
import uz.minibozor.core.design.component.MbListRow
import uz.minibozor.core.design.component.MbLoading
import uz.minibozor.core.design.component.MbPrimaryButton
import uz.minibozor.core.design.component.MbScreen
import uz.minibozor.core.design.component.MbTopBar
import uz.minibozor.core.design.component.MbTotalRow
import uz.minibozor.core.design.component.SectionHeader
import uz.minibozor.core.util.grouped
import uz.minibozor.core.util.sum

/** Screen 19 — Buyurtma berish: address, time, payment and the basket recap. */
@Composable
fun CheckoutScreen(
    viewModel: CheckoutViewModel,
    onBack: () -> Unit,
    onEditAddress: () -> Unit,
    onEditTime: () -> Unit,
    onEditPayment: () -> Unit,
    onConfirm: () -> Unit,
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val preview = state.preview

    MbScreen(
        topBar = { MbTopBar(stringResource(R.string.buyurtma_berish), onBack = onBack) },
        bottomBar = {
            MbBottomBar {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.padding(end = 14.dp)) {
                        MbText(stringResource(R.string.jami), MbTheme.type.meta, MbTheme.colors.icon)
                        MbText(
                            (preview?.totals?.total ?: 0).grouped(),
                            MbTheme.type.price,
                        )
                    }
                    MbPrimaryButton(
                        text = stringResource(R.string.davom_etish),
                        onClick = onConfirm,
                        enabled = state.ready,
                        modifier = Modifier.weight(1f),
                    )
                }
            }
        },
    ) { padding ->
        if (preview == null) {
            MbLoading(Modifier.padding(padding))
            return@MbScreen
        }

        LazyColumn(
            Modifier
                .fillMaxSize()
                .padding(padding),
            contentPadding = PaddingValues(12.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item {
                MbCard(padding = 6.dp) {
                    MbListRow(
                        label = preview.address?.title ?: preview.pickupPoint?.name
                        ?: stringResource(R.string.manzilni_tanlang),
                        glyph = "pin",
                        subtitle = preview.address?.line ?: preview.pickupPoint?.address,
                        onClick = onEditAddress,
                        modifier = Modifier.padding(horizontal = 10.dp),
                    )
                    MbDivider(inset = 62.dp)
                    MbListRow(
                        label = preview.slot?.let { slot ->
                            "${slot.label}"
                        } ?: stringResource(R.string.yetkazish_vaqtini_tanlang),
                        glyph = "clock",
                        subtitle = preview.slot?.note,
                        onClick = onEditTime,
                        modifier = Modifier.padding(horizontal = 10.dp),
                    )
                    MbDivider(inset = 62.dp)
                    MbListRow(
                        label = when {
                            state.paymentMethod == "cash" -> stringResource(R.string.naqd_pul)
                            preview.card != null -> stringResource(R.string.karta_niqob, preview.card.last4)
                            else -> stringResource(R.string.tolov_usulini_tanlang)
                        },
                        glyph = "card",
                        subtitle = if (state.paymentMethod == "cash") {
                            stringResource(R.string.kuryerga_topshirishda)
                        } else preview.card?.brand,
                        onClick = onEditPayment,
                        modifier = Modifier.padding(horizontal = 10.dp),
                    )
                }
            }

            item {
                MbCard {
                    SectionHeader(stringResource(R.string.savat), pluralStringResource(R.plurals.n_products, preview.items.size, preview.items.size))
                    Spacer(Modifier.height(12.dp))
                    preview.items.forEachIndexed { index, item ->
                        MbLineItem(
                            title = item.title,
                            imageUrl = item.imageUrl,
                            meta = item.variantLabel,
                            price = item.unitPrice,
                            quantity = item.quantity,
                        )
                        if (index != preview.items.lastIndex) {
                            Spacer(Modifier.height(14.dp))
                        }
                    }
                }
            }

            item {
                MbCard {
                    MbTotalRow(
                        stringResource(R.string.tovarlar_soni, preview.totals.itemsCount),
                        preview.totals.subtotal.sum(),
                    )
                    if (preview.totals.discount > 0) {
                        MbTotalRow(
                            stringResource(R.string.chegirma),
                            "−${preview.totals.discount.grouped()}",
                            valueColor = MbTheme.colors.success,
                        )
                    }
                    MbTotalRow(
                        stringResource(R.string.yetkazish),
                        if (preview.totals.deliveryFee == 0) stringResource(R.string.bepul)
                        else preview.totals.deliveryFee.sum(),
                        valueColor = if (preview.totals.deliveryFee == 0) MbTheme.colors.success
                        else MbTheme.colors.ink,
                    )
                    MbDivider(Modifier.padding(vertical = 8.dp))
                    MbTotalRow(stringResource(R.string.jami), preview.totals.total.sum(), strong = true)
                }
            }
        }
    }
}
