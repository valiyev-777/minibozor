package uz.minibozor.ui.cart

import androidx.compose.ui.res.pluralStringResource
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
import androidx.compose.foundation.shape.CircleShape
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
import androidx.lifecycle.compose.LifecycleResumeEffect
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import uz.minibozor.R
import uz.minibozor.core.design.MbText
import uz.minibozor.core.design.MbTheme
import uz.minibozor.core.design.mbClickable
import uz.minibozor.core.design.component.MbTabHeader
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
    val cartState by viewModel.cart.collectAsStateWithLifecycle()
    // A plain val, so the null checks below smart-cast.
    val cart = cartState
    val loading by viewModel.loading.collectAsStateWithLifecycle()
    val error by viewModel.error.collectAsStateWithLifecycle()

    // Re-reads whenever the tab comes forward, so a server-side change lands too.
    LifecycleResumeEffect(Unit) {
        viewModel.refresh()
        onPauseOrDispose {}
    }

    MbScreen { padding ->
        Column(
            Modifier
                .fillMaxSize()
                .padding(padding)
        ) {
            MbTabHeader(
                stringResource(R.string.savat),
                trailing = {
                    if (cart != null && cart.items.isNotEmpty()) {
                        MbText(
                            pluralStringResource(R.plurals.n_products, cart.items.size, cart.items.size),
                            MbTheme.type.caption,
                            MbTheme.colors.icon,
                        )
                    }
                },
            )

            when {
                loading && cart == null -> MbLoading()
                error != null && cart == null -> MbErrorState(error!!, viewModel::refresh)
                cart == null || cart.items.isEmpty() -> MbEmptyState(
                    glyph = "cart",
                    title = stringResource(R.string.savat_bosh),
                    message = stringResource(R.string.yoqqan_tovarlarni_savatga_qoshing_keyin_bir),
                    actionLabel = stringResource(R.string.xaridni_boshlash),
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
                                    // Where the shelf ends, not an arbitrary 99:
                                    // plus stops there rather than sending a
                                    // number the server has to quietly cut down.
                                    max = item.stockLeft.coerceAtLeast(1),
                                )
                                Spacer(Modifier.size(6.dp))
                                // Deleting a line sits next to the stepper, as a trash
                                // glyph: the "ret" arrow it replaces was read as "go
                                // back", and an 18 dp icon with no padding around it was
                                // barely hittable. The 40 dp box is the tap target.
                                Box(
                                    Modifier
                                        .size(40.dp)
                                        .mbClickable(CircleShape) { viewModel.remove(item.id) },
                                    contentAlignment = Alignment.Center,
                                ) {
                                    MbIcon(
                                        "trash",
                                        size = 18.dp,
                                        tint = MbTheme.colors.danger,
                                    )
                                }
                                Spacer(Modifier.weight(1f))
                                MbText(
                                    item.lineTotal.sum(),
                                    MbTheme.type.priceSmall,
                                )
                            }
                            if (!item.inStock) {
                                Spacer(Modifier.height(8.dp))
                                MbText(
                                    stringResource(R.string.hozircha_mavjud_emas),
                                    MbTheme.type.caption,
                                    MbTheme.colors.danger,
                                )
                            }
                        }
                    }


                    item {
                        MbCard {
                            MbTotalRow(
                                stringResource(R.string.tovarlar_soni, cart.totals.itemsCount),
                                cart.totals.subtotal.sum(),
                            )
                            if (cart.totals.discount > 0) {
                                MbTotalRow(
                                    stringResource(R.string.chegirma) + (cart.totals.promoCode?.let { " · $it" } ?: ""),
                                    "−${cart.totals.discount.grouped()}",
                                    valueColor = MbTheme.colors.success,
                                )
                            }
                            MbTotalRow(
                                stringResource(R.string.yetkazish),
                                if (cart.totals.deliveryFee == 0L) stringResource(R.string.bepul)
                                else cart.totals.deliveryFee.sum(),
                                valueColor = if (cart.totals.deliveryFee == 0L) {
                                    MbTheme.colors.success
                                } else MbTheme.colors.ink,
                            )
                            if (cart.totals.deliveryFee > 0) {
                                val left = cart.totals.freeDeliveryThreshold - cart.totals.subtotal
                                MbText(
                                    stringResource(R.string.bepul_yetkazishgacha, left.coerceAtLeast(0).sum()),
                                    MbTheme.type.caption,
                                    MbTheme.colors.textQuaternary,
                                )
                            }
                            MbDivider(Modifier.padding(vertical = 8.dp))
                            MbTotalRow(stringResource(R.string.jami), cart.totals.total.sum(), strong = true)
                            Spacer(Modifier.height(12.dp))
                            MbPrimaryButton(
                                text = stringResource(R.string.buyurtma_berish),
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
