package uz.minibozor.ui.cart

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
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.LifecycleResumeEffect
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import uz.minibozor.R
import uz.minibozor.core.design.MbText
import uz.minibozor.core.design.MbTheme
import uz.minibozor.core.design.mbClickable
import uz.minibozor.core.design.strikePrice
import uz.minibozor.core.design.component.MbCard
import uz.minibozor.core.design.component.MbCheckbox
import uz.minibozor.core.design.component.MbDiscountPill
import uz.minibozor.core.design.component.MbDivider
import uz.minibozor.core.design.component.MbEmptyState
import uz.minibozor.core.design.component.MbErrorState
import uz.minibozor.core.design.component.MbLoading
import uz.minibozor.core.design.component.MbLowStock
import uz.minibozor.core.design.component.MbPrimaryButton
import uz.minibozor.core.design.component.MbProductImage
import uz.minibozor.core.design.component.MbQuantityStepper
import uz.minibozor.core.design.component.MbScreen
import uz.minibozor.core.design.component.MbSecondaryButton
import uz.minibozor.core.design.component.MbTabBarSpacer
import uz.minibozor.core.design.component.MbTabHeader
import uz.minibozor.core.design.component.MbTextField
import uz.minibozor.core.design.component.MbTotalRow
import uz.minibozor.core.design.icon.MbIcon
import uz.minibozor.core.util.grouped
import uz.minibozor.core.util.sum
import uz.minibozor.data.remote.dto.CartItemDto

/**
 * Screens 17 (savat) and 18 (bo'sh savat).
 *
 * The basket has to answer three questions without being asked: what is in it,
 * what each of those costs, and what will actually be paid for. The last one is
 * the one the screen used to get wrong — the tick beside every line decides
 * whether that line is counted, the server prices only the ticked ones, and
 * nothing on the screen said so. Unticking a shirt made the total drop with no
 * explanation, and the shirt looked exactly as it had a moment before.
 *
 * So a line that is not counted is dimmed and says so, there is one row at the
 * top that ticks and unticks the lot, and the promo field the server has always
 * accepted is finally on the screen.
 */
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
    val promo by viewModel.promoCode.collectAsStateWithLifecycle()
    val promoError by viewModel.promoError.collectAsStateWithLifecycle()
    val promoBusy by viewModel.promoBusy.collectAsStateWithLifecycle()

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

                else -> {
                    val counted = cart.items.count { it.selected && it.inStock }
                    val countable = cart.items.count { it.inStock }
                    LazyColumn(
                        Modifier.fillMaxSize(),
                        contentPadding = PaddingValues(12.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        // One place to tick and untick the lot.
                        //
                        // A line on the page, not a card: it was a card with a
                        // heading and a sentence of explanation under it, which
                        // is a panel the size of a product tile spent on a
                        // control. What the ticks do is already said on the
                        // lines themselves — an unticked one is dimmed and
                        // carries the reason — so this needs to be no more than
                        // its own label and the count.
                        if (countable > 1) {
                            item(key = "select-all") {
                                Row(
                                    Modifier
                                        .fillMaxWidth()
                                        .mbClickable(MbTheme.shapes.chip) {
                                            viewModel.setAllSelected(counted != countable)
                                        }
                                        .padding(horizontal = 6.dp, vertical = 6.dp),
                                    verticalAlignment = Alignment.CenterVertically,
                                ) {
                                    MbCheckbox(counted == countable)
                                    Spacer(Modifier.width(10.dp))
                                    MbText(
                                        stringResource(R.string.hammasini_tanlash),
                                        MbTheme.type.caption,
                                        MbTheme.colors.inkSoft,
                                        maxLines = 1,
                                        modifier = Modifier.weight(1f),
                                    )
                                    MbText(
                                        "$counted / $countable",
                                        MbTheme.type.meta,
                                        MbTheme.colors.icon,
                                        maxLines = 1,
                                    )
                                }
                            }
                        }

                        items(cart.items, key = { it.id }) { item ->
                            CartLine(
                                item = item,
                                onOpenProduct = { onOpenProduct(item.productId) },
                                onToggleSelected = {
                                    viewModel.setSelected(item.id, !item.selected)
                                },
                                onQuantity = { viewModel.setQuantity(item.id, it) },
                                onRemove = { viewModel.remove(item.id) },
                            )
                        }

                        item(key = "promo") {
                            PromoCard(
                                applied = promo,
                                error = promoError,
                                busy = promoBusy,
                                onApply = viewModel::applyPromo,
                                onClear = viewModel::clearPromo,
                            )
                        }

                        item(key = "totals") {
                            MbCard {
                                MbTotalRow(
                                    stringResource(R.string.tovarlar_soni, cart.totals.itemsCount),
                                    cart.totals.subtotal.sum(),
                                )
                                if (cart.totals.discount > 0) {
                                    MbTotalRow(
                                        stringResource(R.string.chegirma) +
                                            (cart.totals.promoCode?.let { " · $it" } ?: ""),
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
                                    val left =
                                        cart.totals.freeDeliveryThreshold - cart.totals.subtotal
                                    MbText(
                                        stringResource(
                                            R.string.bepul_yetkazishgacha,
                                            left.coerceAtLeast(0).sum(),
                                        ),
                                        MbTheme.type.caption,
                                        MbTheme.colors.textQuaternary,
                                    )
                                }
                                MbDivider(Modifier.padding(vertical = 8.dp))
                                MbTotalRow(
                                    stringResource(R.string.jami),
                                    cart.totals.total.sum(),
                                    strong = true,
                                )
                                Spacer(Modifier.height(12.dp))
                                MbPrimaryButton(
                                    text = stringResource(R.string.buyurtma_berish),
                                    onClick = onCheckout,
                                    enabled = cart.totals.itemsCount > 0,
                                )
                                // Why the button is dark, said where the button
                                // is, rather than left as a dead control.
                                if (cart.totals.itemsCount == 0) {
                                    Spacer(Modifier.height(8.dp))
                                    MbText(
                                        stringResource(R.string.kamida_bitta_tovarni_belgilang),
                                        MbTheme.type.caption,
                                        MbTheme.colors.icon,
                                    )
                                }
                            }
                        }

                        item(key = "tab-spacer") { MbTabBarSpacer() }
                    }
                }
            }
        }
    }
}

/**
 * One line of the basket.
 *
 * Everything about the product itself — its picture, its name, what it costs —
 * is dimmed when the line is not counted, and the controls that change that are
 * not. So an untickd line reads as set aside rather than as broken, and the tick
 * that puts it back is the one thing on it at full strength.
 *
 * The price is given twice on purpose and they are two different numbers: what
 * one of them costs, up beside the name, and what this line comes to, down
 * beside the stepper that decides it. They were both there before with nothing
 * to tell them apart, which on a quantity of one made the card look like it was
 * charging twice.
 */
@Composable
private fun CartLine(
    item: CartItemDto,
    onOpenProduct: () -> Unit,
    onToggleSelected: () -> Unit,
    onQuantity: (Int) -> Unit,
    onRemove: () -> Unit,
) {
    val was = item.oldUnitPrice?.takeIf { it > item.unitPrice }
    val off = was?.let { (((it - item.unitPrice) * 100) / it).toInt() }
    val counted = item.selected && item.inStock
    val fade = if (counted) 1f else 0.45f

    MbCard(padding = 12.dp) {
        Row(verticalAlignment = Alignment.Top) {
            // A 40 dp box around a 22 dp box: the tick decides whether the line
            // is paid for, and it was the smallest target on the screen.
            Box(
                Modifier
                    .size(40.dp)
                    // Dead on a line that cannot be bought: ticking a sold-out
                    // shirt would do nothing to the total, which is a control
                    // that answers a tap by not answering it.
                    .mbClickable(
                        MbTheme.shapes.field,
                        enabled = item.inStock,
                        onClick = onToggleSelected,
                    ),
                contentAlignment = Alignment.Center,
            ) {
                MbCheckbox(counted)
            }
            Row(
                Modifier
                    .weight(1f)
                    .alpha(fade)
                    .mbClickable(MbTheme.shapes.tile, onClick = onOpenProduct)
                    .padding(start = 4.dp, end = 4.dp, top = 2.dp, bottom = 2.dp),
                horizontalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                MbProductImage(
                    item.imageUrl,
                    modifier = Modifier.size(72.dp),
                    shape = MbTheme.shapes.tileSmall,
                )
                Column(Modifier.weight(1f)) {
                    MbText(
                        item.title,
                        MbTheme.type.bodySmall,
                        MbTheme.colors.inkSoft,
                        maxLines = 2,
                    )
                    if (item.variantLabel.isNotBlank()) {
                        Spacer(Modifier.height(3.dp))
                        MbText(
                            item.variantLabel,
                            MbTheme.type.meta,
                            MbTheme.colors.icon,
                            maxLines = 1,
                        )
                    }
                    Spacer(Modifier.height(6.dp))
                    // What one costs. The line's own total lives under the
                    // stepper, which is the thing that decides it.
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        MbText(item.unitPrice.grouped(), MbTheme.type.priceSmall, maxLines = 1)
                        if (was != null) {
                            Spacer(Modifier.width(6.dp))
                            MbText(
                                was.grouped(),
                                MbTheme.type.strikePrice
                                    .copy(textDecoration = TextDecoration.LineThrough),
                                MbTheme.colors.textQuaternary,
                                maxLines = 1,
                            )
                        }
                        if (off != null && off > 0) {
                            Spacer(Modifier.width(6.dp))
                            MbDiscountPill(off)
                        }
                    }
                }
            }
        }

        Spacer(Modifier.height(10.dp))
        Row(verticalAlignment = Alignment.CenterVertically) {
            MbQuantityStepper(
                quantity = item.quantity,
                onChange = onQuantity,
                // Where the shelf ends, not an arbitrary 99: plus stops there
                // rather than sending a number the server has to quietly cut
                // down.
                max = item.stockLeft.coerceAtLeast(1),
            )
            Spacer(Modifier.size(6.dp))
            // Deleting a line sits next to the stepper, as a trash glyph: the
            // "ret" arrow it replaced was read as "go back", and an 18 dp icon
            // with no padding around it was barely hittable. The 40 dp box is
            // the tap target.
            Box(
                Modifier
                    .size(40.dp)
                    .mbClickable(CircleShape, onClick = onRemove),
                contentAlignment = Alignment.Center,
            ) {
                MbIcon("trash", size = 18.dp, tint = MbTheme.colors.danger)
            }
            Spacer(Modifier.weight(1f))
            Column(horizontalAlignment = Alignment.End) {
                if (item.quantity > 1) {
                    MbText(
                        stringResource(R.string.n_ta_uchun, item.quantity),
                        MbTheme.type.micro,
                        MbTheme.colors.icon,
                        maxLines = 1,
                    )
                }
                MbText(
                    item.lineTotal.sum(),
                    MbTheme.type.priceSmall,
                    if (counted) MbTheme.colors.ink else MbTheme.colors.disabled,
                    maxLines = 1,
                )
            }
        }

        // Why a line is not being counted, on the line rather than in the
        // total. The shop's doing — sold out, nearly sold out — reads red; the
        // customer's own untick reads as the quiet note it is.
        val note: Pair<String, Color>? = when {
            !item.inStock ->
                stringResource(R.string.hozircha_mavjud_emas) to MbTheme.colors.danger
            !item.selected ->
                stringResource(R.string.belgilanmagan_hisobga_olinmaydi) to MbTheme.colors.icon
            item.stockLeft in 1..MbLowStock ->
                stringResource(R.string.n_dona_qoldi, item.stockLeft) to MbTheme.colors.danger
            else -> null
        }
        if (note != null) {
            Spacer(Modifier.height(8.dp))
            MbText(note.first, MbTheme.type.caption, note.second, maxLines = 1)
        }
    }
}

/**
 * The promo code, on the screen at last.
 *
 * The server has taken one since the first endpoint was written, the cart
 * repository has had a call for it, and the field was imported into this file
 * and never drawn — so a customer with a code had no way to spend it. Applied,
 * the field is replaced by the code itself and a way to take it back off, which
 * is the difference between a discount that happened and a box that was typed
 * in.
 */
@Composable
private fun PromoCard(
    applied: String?,
    error: String?,
    busy: Boolean,
    onApply: (String) -> Unit,
    onClear: () -> Unit,
) {
    var code by remember { mutableStateOf("") }

    MbCard(padding = 12.dp) {
        if (applied != null) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                MbIcon("ticket", size = 18.dp, tint = MbTheme.colors.success)
                Spacer(Modifier.width(10.dp))
                MbText(
                    stringResource(R.string.promokod_qollandi, applied),
                    MbTheme.type.label,
                    MbTheme.colors.ink,
                    modifier = Modifier.weight(1f),
                    maxLines = 1,
                )
                MbText(
                    stringResource(R.string.bekor_qilish),
                    MbTheme.type.label,
                    MbTheme.colors.accent,
                    modifier = Modifier
                        .mbClickable(MbTheme.shapes.chip) {
                            code = ""
                            onClear()
                        }
                        .padding(horizontal = 8.dp, vertical = 6.dp),
                )
            }
        } else {
            Row(
                verticalAlignment = Alignment.Top,
                horizontalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                MbTextField(
                    value = code,
                    onValueChange = { code = it.uppercase() },
                    placeholder = stringResource(R.string.promokod),
                    leadingGlyph = "ticket",
                    error = error,
                    modifier = Modifier.weight(1f),
                )
                MbSecondaryButton(
                    text = stringResource(R.string.qollash),
                    onClick = { onApply(code) },
                    enabled = code.isNotBlank() && !busy,
                    modifier = Modifier.width(104.dp),
                )
            }
        }
    }
}
