package uz.minibozor.ui.cart

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
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.runtime.Composable
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
import uz.minibozor.core.design.component.MbCheckbox
import uz.minibozor.core.design.component.MbDivider
import uz.minibozor.core.design.component.MbEmptyState
import uz.minibozor.core.design.component.MbErrorState
import uz.minibozor.core.design.component.MbLineItem
import uz.minibozor.core.design.component.MbLoading
import uz.minibozor.core.design.component.MbPrimaryButton
import uz.minibozor.core.design.component.MbQuantityStepper
import uz.minibozor.core.design.component.MbScreen
import uz.minibozor.core.design.component.MbTabBarSpacer
import uz.minibozor.core.design.component.MbTextField
import uz.minibozor.core.design.component.MbTotalRow
import uz.minibozor.core.design.icon.MbIcon
import uz.minibozor.core.util.grouped
import uz.minibozor.core.util.sum

/** Screens 17 (savat) and 18 (bo'sh savat). */
@Composable
fun CartScreen(
    onCheckout: () -> Unit,
    onOpenProduct: (Int) -> Unit,
    onStartShopping: () -> Unit,
    viewModel: CartViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val cart = state.cart

    MbScreen { padding ->
        Column(
            Modifier
                .fillMaxSize()
                .padding(padding)
        ) {
            Row(
                Modifier
                    .fillMaxWidth()
                    .background(MbTheme.colors.surface)
                    .padding(horizontal = 20.dp, vertical = 14.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                MbText("Savat", MbTheme.type.title1)
                Spacer(Modifier.weight(1f))
                if (cart != null && cart.items.isNotEmpty()) {
                    MbText(
                        "${cart.items.size} tovar",
                        MbTheme.type.caption,
                        MbTheme.colors.icon,
                    )
                }
            }

            when {
                state.loading && cart == null -> MbLoading()
                state.error != null && cart == null ->
                    MbErrorState(state.error!!, viewModel::refresh)
                cart == null || cart.items.isEmpty() -> MbEmptyState(
                    glyph = "cart",
                    title = "Savat bo'sh",
                    message = "Yoqqan tovarlarni savatga qo'shing — " +
                        "keyin bir marta buyurtma berasiz.",
                    actionLabel = "Xaridni boshlash",
                    onAction = onStartShopping,
                )

                else -> LazyColumn(
                    Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(12.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    items(cart.items, key = { it.id }) { item ->
                        MbCard(padding = 14.dp) {
                            Row(verticalAlignment = Alignment.Top) {
                                Box(
                                    Modifier
                                        .padding(end = 12.dp, top = 4.dp)
                                        .clickable {
                                            viewModel.setSelected(item.id, !item.selected)
                                        }
                                ) {
                                    MbCheckbox(item.selected)
                                }
                                MbLineItem(
                                    title = item.title,
                                    imageUrl = item.imageUrl,
                                    meta = item.variantLabel,
                                    price = item.unitPrice,
                                    onClick = { onOpenProduct(item.productId) },
                                    modifier = Modifier.weight(1f),
                                )
                            }
                            Spacer(Modifier.height(12.dp))
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                MbQuantityStepper(
                                    quantity = item.quantity,
                                    onChange = { viewModel.setQuantity(item.id, it) },
                                )
                                Spacer(Modifier.weight(1f))
                                MbText(
                                    item.lineTotal.sum(),
                                    MbTheme.type.priceSmall,
                                )
                                Spacer(Modifier.size(14.dp))
                                MbIcon(
                                    "ret",
                                    size = 18.dp,
                                    tint = MbTheme.colors.icon,
                                    modifier = Modifier.clickable { viewModel.remove(item.id) },
                                )
                            }
                            if (!item.inStock) {
                                Spacer(Modifier.height(8.dp))
                                MbText(
                                    "Hozircha mavjud emas",
                                    MbTheme.type.caption,
                                    MbTheme.colors.danger,
                                )
                            }
                        }
                    }

                    item {
                        MbCard {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                MbTextField(
                                    value = state.promoInput,
                                    onValueChange = viewModel::onPromoChange,
                                    placeholder = "Promokod",
                                    leadingGlyph = "ticket",
                                    error = state.promoError,
                                    modifier = Modifier.weight(1f),
                                )
                                Spacer(Modifier.size(10.dp))
                                Box(
                                    Modifier
                                        .clip(MbTheme.shapes.field)
                                        .background(MbTheme.colors.ink)
                                        .clickable(onClick = viewModel::applyPromo)
                                        .padding(horizontal = 18.dp, vertical = 14.dp)
                                ) {
                                    MbText(
                                        "Qo'llash",
                                        MbTheme.type.label,
                                        androidx.compose.ui.graphics.Color.White,
                                    )
                                }
                            }
                        }
                    }

                    item {
                        MbCard {
                            MbTotalRow(
                                "Tovarlar (${cart.totals.itemsCount})",
                                cart.totals.subtotal.sum(),
                            )
                            if (cart.totals.discount > 0) {
                                MbTotalRow(
                                    "Chegirma" + (cart.totals.promoCode?.let { " · $it" } ?: ""),
                                    "−${cart.totals.discount.grouped()}",
                                    valueColor = MbTheme.colors.success,
                                )
                            }
                            MbTotalRow(
                                "Yetkazish",
                                if (cart.totals.deliveryFee == 0) "Bepul"
                                else cart.totals.deliveryFee.sum(),
                                valueColor = if (cart.totals.deliveryFee == 0) {
                                    MbTheme.colors.success
                                } else MbTheme.colors.ink,
                            )
                            if (cart.totals.deliveryFee > 0) {
                                val left = cart.totals.freeDeliveryThreshold - cart.totals.subtotal
                                MbText(
                                    "Yana ${left.coerceAtLeast(0).sum()} qo'shsangiz — bepul yetkazish",
                                    MbTheme.type.caption,
                                    MbTheme.colors.textQuaternary,
                                )
                            }
                            MbDivider(Modifier.padding(vertical = 8.dp))
                            MbTotalRow("Jami", cart.totals.total.sum(), strong = true)
                            Spacer(Modifier.height(12.dp))
                            MbPrimaryButton(
                                text = "Buyurtma berish",
                                onClick = onCheckout,
                                enabled = cart.totals.itemsCount > 0,
                            )
                        }
                    }

                    item { MbTabBarSpacer() }
                }
            }
        }
    }
}
