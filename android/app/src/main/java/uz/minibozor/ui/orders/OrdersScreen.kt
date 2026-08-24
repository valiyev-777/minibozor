package uz.minibozor.ui.orders

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
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import uz.minibozor.core.design.MbText
import uz.minibozor.core.design.MbTheme
import uz.minibozor.core.design.component.MbCard
import uz.minibozor.core.design.component.MbDivider
import uz.minibozor.core.design.component.MbEmptyState
import uz.minibozor.core.design.component.MbErrorState
import uz.minibozor.core.design.component.MbLoading
import uz.minibozor.core.design.component.MbProductImage
import uz.minibozor.core.design.component.MbSecondaryButton
import uz.minibozor.core.design.component.MbStatusPill
import uz.minibozor.core.design.component.MbScreen
import uz.minibozor.core.design.component.MbTopBar
import uz.minibozor.core.util.sum
import uz.minibozor.data.remote.dto.OrderSummaryDto

/** Screen 26 — Buyurtmalarim. */
@Composable
fun OrdersScreen(
    onBack: () -> Unit,
    onOpenOrder: (Int) -> Unit,
    onTrack: (Int) -> Unit,
    onStartShopping: () -> Unit,
    viewModel: OrdersViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()

    MbScreen(topBar = { MbTopBar("Buyurtmalarim", onBack = onBack) }) { padding ->
        Column(
            Modifier
                .fillMaxSize()
                .padding(padding)
        ) {
            Row(
                Modifier
                    .fillMaxWidth()
                    .background(MbTheme.colors.surface)
                    .padding(horizontal = 14.dp, vertical = 10.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                SegmentTab("Jarayonda", state.activeTab, Modifier.weight(1f)) {
                    viewModel.selectTab(true)
                }
                SegmentTab("Tugagan", !state.activeTab, Modifier.weight(1f)) {
                    viewModel.selectTab(false)
                }
            }

            when {
                state.loading -> MbLoading()
                state.error != null -> MbErrorState(state.error!!, viewModel::load)
                state.orders.isEmpty() -> MbEmptyState(
                    glyph = "box",
                    title = if (state.activeTab) "Faol buyurtma yo'q" else "Tugagan buyurtma yo'q",
                    message = "Buyurtma bergach, holati shu yerda ko'rinadi.",
                    actionLabel = "Xaridni boshlash",
                    onAction = onStartShopping,
                )

                else -> LazyColumn(
                    contentPadding = PaddingValues(12.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    items(state.orders, key = { it.id }) { order ->
                        OrderCard(order, onOpenOrder, onTrack)
                    }
                }
            }
        }
    }
}

@Composable
private fun OrderCard(
    order: OrderSummaryDto,
    onOpen: (Int) -> Unit,
    onTrack: (Int) -> Unit,
) {
    MbCard(Modifier.clickable { onOpen(order.id) }) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            MbStatusPill(
                label = order.statusLabel,
                background = statusBackground(order.status),
                contentColor = statusColor(order.status),
            )
            Spacer(Modifier.weight(1f))
            MbText(order.code, MbTheme.type.caption, MbTheme.colors.icon)
        }

        Spacer(Modifier.height(14.dp))
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            order.previewImages.take(2).forEach { image ->
                MbProductImage(
                    image,
                    modifier = Modifier.size(56.dp),
                    shape = MbTheme.shapes.tileSmall,
                )
            }
            val extra = order.itemsCount - order.previewImages.take(2).size
            if (extra > 0) {
                Box(
                    Modifier
                        .size(56.dp)
                        .clip(MbTheme.shapes.tileSmall)
                        .background(MbTheme.colors.fill),
                    contentAlignment = Alignment.Center,
                ) {
                    MbText("+$extra", MbTheme.type.label, MbTheme.colors.textSecondary)
                }
            }
            Spacer(Modifier.weight(1f))
            Column(horizontalAlignment = Alignment.End) {
                MbText("Jami", MbTheme.type.meta, MbTheme.colors.icon)
                MbText(order.total.sum(), MbTheme.type.priceSmall)
            }
        }

        Spacer(Modifier.height(12.dp))
        MbDivider()
        Spacer(Modifier.height(12.dp))
        Row(verticalAlignment = Alignment.CenterVertically) {
            MbText(
                order.etaLabel,
                MbTheme.type.caption,
                MbTheme.colors.textSecondary,
                modifier = Modifier.weight(1f),
            )
            if (order.canTrack) {
                MbSecondaryButton(
                    text = "Kuzatish",
                    onClick = { onTrack(order.id) },
                    modifier = Modifier.width(120.dp),
                )
            }
        }
    }
}

@Composable
private fun SegmentTab(
    label: String,
    selected: Boolean,
    modifier: Modifier = Modifier,
    onClick: () -> Unit,
) {
    Box(
        modifier
            .clip(MbTheme.shapes.field)
            .background(if (selected) MbTheme.colors.ink else MbTheme.colors.fill)
            .clickable(onClick = onClick)
            .padding(vertical = 11.dp),
        contentAlignment = Alignment.Center,
    ) {
        MbText(
            label,
            MbTheme.type.label,
            if (selected) Color.White else MbTheme.colors.textSecondary,
        )
    }
}

@Composable
internal fun statusBackground(status: String) = when (status) {
    "packing" -> MbTheme.colors.warningBg
    "delivered" -> MbTheme.colors.successBg
    "cancelled", "returned" -> MbTheme.colors.dangerBg
    else -> MbTheme.colors.fillCool
}

@Composable
internal fun statusColor(status: String) = when (status) {
    "packing" -> MbTheme.colors.warning
    "delivered" -> MbTheme.colors.success
    "cancelled", "returned" -> MbTheme.colors.danger
    else -> MbTheme.colors.accent
}
