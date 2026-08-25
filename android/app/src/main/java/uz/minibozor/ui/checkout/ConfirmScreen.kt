package uz.minibozor.ui.checkout

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import uz.minibozor.R
import uz.minibozor.core.design.MbText
import uz.minibozor.core.design.MbTheme
import uz.minibozor.core.design.component.MbBottomBar
import uz.minibozor.core.design.component.MbCard
import uz.minibozor.core.design.component.MbDivider
import uz.minibozor.core.design.component.MbListRow
import uz.minibozor.core.design.component.MbLoading
import uz.minibozor.core.design.component.MbPrimaryButton
import uz.minibozor.core.design.component.MbScreen
import uz.minibozor.core.design.component.MbTopBar
import uz.minibozor.core.design.component.MbTotalRow
import uz.minibozor.core.util.grouped
import uz.minibozor.core.util.sum

/** Screen 23 — the last look before the money moves. */
@Composable
fun ConfirmScreen(
    viewModel: CheckoutViewModel,
    onBack: () -> Unit,
    onPlaced: (Int) -> Unit,
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val preview = state.preview

    LaunchedEffect(state.placedOrderId) {
        state.placedOrderId?.let(onPlaced)
    }

    MbScreen(
        topBar = { MbTopBar(stringResource(R.string.tolovni_tasdiqlash), onBack = onBack) },
        bottomBar = {
            MbBottomBar {
                MbPrimaryButton(
                    text = if (state.paymentMethod == "cash") {
                        stringResource(R.string.buyurtmani_rasmiylashtirish)
                    } else {
                        stringResource(R.string.tolash_n, (preview?.totals?.total ?: 0).grouped())
                    },
                    onClick = viewModel::place,
                    enabled = state.ready,
                    loading = state.placing,
                )
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
                        label = preview.address?.line ?: preview.pickupPoint?.name.orEmpty(),
                        glyph = "pin",
                        subtitle = preview.address?.meta ?: preview.pickupPoint?.address,
                        showChevron = false,
                        modifier = Modifier.padding(horizontal = 10.dp),
                    )
                    MbDivider(inset = 62.dp)
                    MbListRow(
                        label = preview.slot?.label ?: stringResource(R.string.punktdan_olish),
                        glyph = "clock",
                        subtitle = preview.slot?.note,
                        showChevron = false,
                        modifier = Modifier.padding(horizontal = 10.dp),
                    )
                    MbDivider(inset = 62.dp)
                    MbListRow(
                        label = if (state.paymentMethod == "cash") stringResource(R.string.naqd_pul)
                        else stringResource(R.string.karta_niqob, preview.card?.last4.orEmpty()),
                        glyph = "card",
                        subtitle = if (state.paymentMethod == "cash") {
                            stringResource(R.string.kuryerga_topshirishda)
                        } else preview.card?.brand,
                        showChevron = false,
                        modifier = Modifier.padding(horizontal = 10.dp),
                    )
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
                    )
                    MbDivider(Modifier.padding(vertical = 8.dp))
                    MbTotalRow(stringResource(R.string.tolanadi), preview.totals.total.sum(), strong = true)
                }
            }

            if (state.error != null) {
                item {
                    MbText(
                        state.error!!,
                        MbTheme.type.caption,
                        MbTheme.colors.danger,
                        modifier = Modifier.padding(horizontal = 6.dp),
                    )
                }
            }

            item {
                MbText(
                    stringResource(R.string.tugmani_bosish_orqali_ommaviy_oferta),
                    MbTheme.type.caption,
                    MbTheme.colors.textQuaternary,
                    textAlign = TextAlign.Center,
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 20.dp),
                )
            }
        }
    }
}
