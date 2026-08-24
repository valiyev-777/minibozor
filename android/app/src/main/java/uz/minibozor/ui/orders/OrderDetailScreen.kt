package uz.minibozor.ui.orders

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import uz.minibozor.core.design.MbText
import uz.minibozor.core.design.MbTheme
import uz.minibozor.core.design.component.MbCard
import uz.minibozor.core.design.component.MbDivider
import uz.minibozor.core.design.component.MbErrorState
import uz.minibozor.core.design.component.MbKeyValueRow
import uz.minibozor.core.design.component.MbLineItem
import uz.minibozor.core.design.component.MbLoading
import uz.minibozor.core.design.component.MbScreen
import uz.minibozor.core.design.component.MbSecondaryButton
import uz.minibozor.core.design.component.MbStatusPill
import uz.minibozor.core.design.component.MbTopBar
import uz.minibozor.core.design.component.MbTotalRow
import uz.minibozor.core.design.component.SectionHeader
import uz.minibozor.core.util.grouped
import uz.minibozor.core.util.sum
import uz.minibozor.core.util.toLocalDateTimeOrNull
import uz.minibozor.core.util.uzDateTime
import uz.minibozor.data.remote.dto.OrderEventDto

/** Screens 25 (tracking) and 27 (full detail) — the same data, different depth. */
@Composable
fun OrderDetailScreen(
    orderId: Int,
    trackingOnly: Boolean,
    onBack: () -> Unit,
    onCancel: (Int) -> Unit,
    onReturn: (Int) -> Unit,
    onWriteReview: (productId: Int, orderItemId: Int) -> Unit,
    viewModel: OrderDetailViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    LaunchedEffect(orderId) { viewModel.load(orderId) }
    val order = state.order

    MbScreen(
        topBar = {
            MbTopBar(
                title = if (trackingOnly) "Yetkazish holati" else "Buyurtma tafsilotlari",
                subtitle = order?.code,
                onBack = onBack,
            )
        },
    ) { padding ->
        when {
            state.loading && order == null -> MbLoading(Modifier.padding(padding))
            state.error != null && order == null ->
                MbErrorState(state.error!!, viewModel::retry, Modifier.padding(padding))
            order == null -> Unit
            else -> LazyColumn(
                Modifier
                    .fillMaxSize()
                    .padding(padding),
                contentPadding = PaddingValues(12.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                item {
                    MbCard {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            MbStatusPill(
                                order.statusLabel,
                                statusBackground(order.status),
                                statusColor(order.status),
                            )
                            Spacer(Modifier.weight(1f))
                            MbText(order.etaLabel, MbTheme.type.caption, MbTheme.colors.icon)
                        }
                        Spacer(Modifier.height(16.dp))
                        order.events.forEachIndexed { index, event ->
                            TimelineRow(event, isLast = index == order.events.lastIndex)
                        }
                    }
                }

                item {
                    MbCard {
                        SectionHeader("Tovarlar", "${order.itemsCount} ta")
                        Spacer(Modifier.height(12.dp))
                        order.items.forEachIndexed { index, item ->
                            MbLineItem(
                                title = item.title,
                                imageUrl = item.imageUrl,
                                meta = item.variantLabel,
                                price = item.unitPrice,
                                quantity = item.quantity,
                                trailing = {
                                    if (order.status == "delivered" && !item.reviewed &&
                                        item.productId != null
                                    ) {
                                        MbSecondaryButton(
                                            text = "Sharh",
                                            onClick = { onWriteReview(item.productId, item.id) },
                                            modifier = Modifier.width(88.dp),
                                        )
                                    }
                                },
                            )
                            if (index != order.items.lastIndex) Spacer(Modifier.height(14.dp))
                        }
                    }
                }

                if (!trackingOnly) {
                    item {
                        MbCard {
                            SectionHeader("Ma'lumot")
                            Spacer(Modifier.height(4.dp))
                            MbKeyValueRow(
                                "Buyurtma sanasi",
                                order.createdAt.toLocalDateTimeOrNull()?.uzDateTime().orEmpty(),
                            )
                            MbKeyValueRow("To'lov", order.paymentLabel)
                            MbKeyValueRow(
                                "Manzil",
                                listOf(order.addressLine, order.addressMeta)
                                    .filter { it.isNotBlank() }
                                    .joinToString(", "),
                            )
                            MbKeyValueRow(
                                "Qabul qiluvchi",
                                "${order.recipientName}, ${order.recipientPhone}",
                            )
                        }
                    }

                    item {
                        MbCard {
                            MbTotalRow("Tovarlar", order.subtotal.sum())
                            if (order.discount > 0) {
                                MbTotalRow(
                                    "Chegirma",
                                    "−${order.discount.grouped()}",
                                    valueColor = MbTheme.colors.success,
                                )
                            }
                            MbTotalRow(
                                "Yetkazish",
                                if (order.deliveryFee == 0) "Bepul" else order.deliveryFee.sum(),
                            )
                            MbDivider(Modifier.padding(vertical = 8.dp))
                            MbTotalRow("Jami", order.total.sum(), strong = true)
                        }
                    }

                    if (order.canCancel || order.status == "delivered") {
                        item {
                            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                                if (order.canCancel) {
                                    MbSecondaryButton(
                                        "Buyurtmani bekor qilish",
                                        { onCancel(order.id) },
                                        contentColor = MbTheme.colors.danger,
                                    )
                                }
                                if (order.status == "delivered") {
                                    MbSecondaryButton(
                                        "Qaytarish arizasi",
                                        { onReturn(order.id) },
                                    )
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun TimelineRow(event: OrderEventDto, isLast: Boolean) {
    Row {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Box(
                Modifier
                    .size(12.dp)
                    .clip(CircleShape)
                    .background(
                        if (event.done) MbTheme.colors.accent else MbTheme.colors.divider
                    )
            )
            if (!isLast) {
                Box(
                    Modifier
                        .width(1.5.dp)
                        .height(34.dp)
                        .background(
                            if (event.done) MbTheme.colors.accent.copy(alpha = 0.35f)
                            else MbTheme.colors.border
                        )
                )
            }
        }
        Spacer(Modifier.width(12.dp))
        Column(Modifier.padding(bottom = if (isLast) 0.dp else 8.dp)) {
            MbText(
                event.title,
                MbTheme.type.body.copy(
                    fontWeight = androidx.compose.ui.text.font.FontWeight.Bold),
                if (event.done) MbTheme.colors.ink else MbTheme.colors.disabled,
            )
            val stamp = event.happenedAt?.toLocalDateTimeOrNull()?.uzDateTime()
            MbText(
                stamp ?: event.note.ifBlank { "Kutilmoqda" },
                MbTheme.type.meta,
                MbTheme.colors.icon,
            )
        }
    }
}
