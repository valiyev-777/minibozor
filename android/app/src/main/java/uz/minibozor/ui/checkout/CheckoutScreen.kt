package uz.minibozor.ui.checkout

import androidx.compose.foundation.background
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
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import uz.minibozor.R
import uz.minibozor.core.design.MbText
import uz.minibozor.core.design.MbTheme
import uz.minibozor.core.design.component.MbBottomBar
import uz.minibozor.core.design.component.MbCard
import uz.minibozor.core.design.component.MbDivider
import uz.minibozor.core.design.component.MbLoading
import uz.minibozor.core.design.component.MbPhotoStack
import uz.minibozor.core.design.component.MbPrimaryButton
import uz.minibozor.core.design.component.MbScreen
import uz.minibozor.core.design.component.MbTopBar
import uz.minibozor.core.design.component.MbTotalRow
import uz.minibozor.core.design.component.SectionHeader
import uz.minibozor.core.design.icon.MbIcon
import uz.minibozor.core.design.mbClickable
import uz.minibozor.core.util.grouped
import uz.minibozor.core.util.sum

/**
 * Screen 19 — Rasmiylashtirish.
 *
 * The screen was three grey rows and a button that went dark until all three
 * were filled. It never said which of them was missing, never said what
 * delivery would cost or why it could not say yet, and offered no choice
 * between a courier and a counter even though the order it builds carries one.
 * A customer who could not work out why the button would not press had nowhere
 * to look.
 *
 * So it is built around what is still missing rather than around what has been
 * filled in. The rails at the top say how far along this is. Each step that has
 * not been answered draws as a dashed frame with the question on it, and the
 * one that cannot be answered yet says what it is waiting for instead of
 * sitting there greyed and mute. The button at the bottom is never disabled: it
 * carries the name of the next thing to do, and only becomes "Tasdiqlash" when
 * there is nothing left to ask.
 */
@Composable
fun CheckoutScreen(
    viewModel: CheckoutViewModel,
    onBack: () -> Unit,
    onEditAddress: () -> Unit,
    onEditTime: () -> Unit,
    onEditPayment: () -> Unit,
    onOpenCart: () -> Unit,
    onConfirm: () -> Unit,
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val preview = state.preview
    val courier = state.delivery == DeliveryMethod.Courier

    MbScreen(
        topBar = { MbTopBar(stringResource(R.string.rasmiylashtirish), onBack = onBack) },
        bottomBar = {
            MbBottomBar {
                // What is left, in words, above the button that asks for it.
                // Between the two, someone who cannot proceed can always find
                // out why without pressing anything.
                MbText(
                    if (state.ready) {
                        stringResource(R.string.hammasi_tayyor)
                    } else {
                        pluralStringResource(
                            R.plurals.n_qadam_qoldi,
                            state.missing.size,
                            state.missing.size,
                        )
                    },
                    MbTheme.type.meta,
                    if (state.ready) MbTheme.colors.success else MbTheme.colors.icon,
                    maxLines = 1,
                    modifier = Modifier.padding(bottom = 9.dp),
                )
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.padding(end = 14.dp)) {
                        MbText(
                            stringResource(R.string.tolanadi),
                            MbTheme.type.meta,
                            MbTheme.colors.icon,
                        )
                        MbText((preview?.totals?.total ?: 0).grouped(), MbTheme.type.price)
                    }
                    // Never disabled. A button that has gone dark is a dead end
                    // with no explanation on it; a button that says "Manzil
                    // qo'shish" is the way out of the same state.
                    MbPrimaryButton(
                        text = when (state.nextStep) {
                            CheckoutStep.Address ->
                                if (courier) stringResource(R.string.manzil_qoshish)
                                else stringResource(R.string.punkt_tanlash)
                            CheckoutStep.Time -> stringResource(R.string.yetkazish_vaqti_qisqa)
                            CheckoutStep.Payment -> stringResource(R.string.karta_qoshish)
                            null -> stringResource(R.string.davom_etish)
                        },
                        onClick = {
                            when (state.nextStep) {
                                CheckoutStep.Address -> onEditAddress()
                                CheckoutStep.Time -> onEditTime()
                                CheckoutStep.Payment -> onEditPayment()
                                null -> onConfirm()
                            }
                        },
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
            // The basket, folded down to what it is rather than listed out.
            // Whoever reached this screen has just come from the cart and knows
            // what is in it; what they want here is reassurance that it is the
            // same basket, and a way back if it is not.
            item {
                MbCard(padding = 14.dp) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        MbPhotoStack(
                            photos = preview.items.mapNotNull { it.imageUrl },
                            total = preview.items.size,
                            tile = 44.dp,
                        )
                        Spacer(Modifier.size(12.dp))
                        Column(Modifier.weight(1f)) {
                            MbText(
                                pluralStringResource(
                                    R.plurals.n_products,
                                    preview.totals.itemsCount,
                                    preview.totals.itemsCount,
                                ),
                                MbTheme.type.label,
                            )
                            MbText(
                                preview.items.joinToString(", ") { it.title },
                                MbTheme.type.meta,
                                MbTheme.colors.icon,
                                maxLines = 1,
                            )
                        }
                        MbText(
                            stringResource(R.string.korish),
                            MbTheme.type.label,
                            MbTheme.colors.accent,
                            modifier = Modifier
                                .clip(MbTheme.shapes.chip)
                                .mbClickable(MbTheme.shapes.chip, onClick = onOpenCart)
                                .padding(horizontal = 8.dp, vertical = 5.dp),
                        )
                    }
                }
            }

            item {
                MbCard {
                    SectionHeader(stringResource(R.string.yetkazish_usuli))
                    Spacer(Modifier.height(12.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        MethodTile(
                            title = stringResource(R.string.kuryer),
                            note = stringResource(R.string.kuryer_izoh),
                            selected = courier,
                            onClick = { viewModel.selectDelivery(DeliveryMethod.Courier) },
                            modifier = Modifier.weight(1f),
                        )
                        MethodTile(
                            title = stringResource(R.string.punktdan_olish),
                            note = stringResource(R.string.punktdan_olish_izoh),
                            selected = !courier,
                            onClick = { viewModel.selectDelivery(DeliveryMethod.Pickup) },
                            modifier = Modifier.weight(1f),
                        )
                    }

                    Spacer(Modifier.height(14.dp))
                    val where = if (courier) state.selectedAddress else null
                    val point = if (courier) null else state.selectedPickup
                    StepRow(
                        glyph = "pin",
                        title = when {
                            where != null -> where.title
                            point != null -> point.name
                            courier -> stringResource(R.string.manzil_kiritilmagan)
                            else -> stringResource(R.string.punkt_tanlanmagan)
                        },
                        subtitle = when {
                            where != null -> where.line
                            point != null -> point.address
                            courier -> stringResource(R.string.xaritada_joyni_belgilang)
                            else -> stringResource(R.string.ozingizga_qulay_punktni_tanlang)
                        },
                        action = when {
                            where != null || point != null -> null
                            courier -> stringResource(R.string.manzil_qoshish)
                            else -> stringResource(R.string.punkt_tanlash)
                        },
                        onClick = onEditAddress,
                    )

                    // Only a courier order has a time to choose, and only once
                    // there is somewhere to take it. Locked rather than hidden:
                    // a step that vanishes and comes back is a step nobody
                    // knows is coming.
                    if (courier) {
                        val hasAddress = state.addressId != null
                        Spacer(Modifier.height(10.dp))
                        StepRow(
                            glyph = "clock",
                            title = preview.slot?.label
                                ?: stringResource(R.string.yetkazish_vaqti_qisqa),
                            subtitle = preview.slot?.note ?: stringResource(
                                // Three states, not two: waiting on the address,
                                // ready to be asked, and answered. Telling
                                // someone who has just typed their address that
                                // the step needs an address is the screen not
                                // keeping up with them.
                                if (hasAddress) {
                                    R.string.yetkazish_vaqtini_tanlang
                                } else {
                                    R.string.manzil_kiritilgandan_keyin
                                }
                            ),
                            action = if (hasAddress && preview.slot == null) {
                                stringResource(R.string.tanlash)
                            } else {
                                null
                            },
                            enabled = hasAddress,
                            onClick = onEditTime,
                        )
                    }
                }
            }

            item {
                MbCard {
                    SectionHeader(stringResource(R.string.tolov))
                    Spacer(Modifier.height(12.dp))
                    val cash = state.paymentMethod == "cash"
                    StepRow(
                        glyph = "card",
                        title = when {
                            cash -> stringResource(R.string.naqd_pul)
                            preview.card != null ->
                                stringResource(R.string.karta_niqob, preview.card.last4)
                            else -> stringResource(R.string.karta_qoshilmagan)
                        },
                        subtitle = when {
                            cash -> stringResource(R.string.kuryerga_topshirishda)
                            preview.card != null -> preview.card.brand
                            else -> stringResource(R.string.karta_yoki_naqd)
                        },
                        action = if (cash || preview.card != null) {
                            null
                        } else {
                            stringResource(R.string.karta_qoshish)
                        },
                        onClick = onEditPayment,
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
                            valueColor = MbTheme.colors.danger,
                        )
                    }
                    // "aniqlanadi" rather than a confident nothing. Printing
                    // "bepul" against an order with no address on it is a price
                    // the shop has not worked out yet, and a customer who reads
                    // it as a promise has been told something untrue.
                    // Priced once the shop knows where this is going — which
                    // is an address for a courier and a counter for a pickup.
                    // Neither is "somewhere", and a fee against neither is a
                    // number carried over from the last time it did know.
                    val priced =
                        if (courier) state.addressId != null else state.pickupPointId != null
                    MbTotalRow(
                        stringResource(R.string.yetkazish),
                        when {
                            !priced -> stringResource(R.string.aniqlanadi)
                            preview.totals.deliveryFee == 0L -> stringResource(R.string.bepul)
                            else -> preview.totals.deliveryFee.sum()
                        },
                        valueColor = when {
                            !priced -> MbTheme.colors.disabled
                            preview.totals.deliveryFee == 0L -> MbTheme.colors.success
                            else -> MbTheme.colors.ink
                        },
                    )
                    MbDivider(Modifier.padding(vertical = 8.dp))
                    MbTotalRow(
                        stringResource(R.string.tolanadi),
                        preview.totals.total.sum(),
                        strong = true,
                    )
                    if (!priced) {
                        Spacer(Modifier.height(6.dp))
                        MbText(
                            stringResource(
                                if (courier) {
                                    R.string.yetkazish_narxi_manzildan_keyin
                                } else {
                                    R.string.yetkazish_narxi_punktdan_keyin
                                }
                            ),
                            MbTheme.type.meta,
                            MbTheme.colors.icon,
                        )
                    }
                }
            }
        }
    }
}

/** One of the two delivery methods, as a tile that reads as chosen or not. */
@Composable
private fun MethodTile(
    title: String,
    note: String,
    selected: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    // Read here rather than inside `drawBehind`, which is not a composable
    // scope and cannot reach the theme.
    val border = if (selected) MbTheme.colors.ink else MbTheme.colors.border
    Column(
        modifier
            .clip(MbTheme.shapes.field)
            .background(if (selected) MbTheme.colors.fill else MbTheme.colors.surface)
            .mbClickable(MbTheme.shapes.field, onClick = onClick)
            .drawBehind {
                drawRoundRect(
                    color = border,
                    style = Stroke(if (selected) 1.6.dp.toPx() else 1.dp.toPx()),
                    cornerRadius = CornerRadius(14.dp.toPx()),
                )
            }
            .padding(horizontal = 12.dp, vertical = 11.dp),
    ) {
        MbText(
            title,
            MbTheme.type.label,
            if (selected) MbTheme.colors.ink else MbTheme.colors.inkMuted,
            maxLines = 1,
        )
        Spacer(Modifier.height(2.dp))
        MbText(
            note,
            MbTheme.type.meta,
            if (selected) MbTheme.colors.icon else MbTheme.colors.disabled,
            maxLines = 1,
        )
    }
}

/**
 * A step of the order: answered, unanswered, or not yet askable.
 *
 * Unanswered draws dashed, which is the one border in the app that reads as a
 * blank waiting to be filled rather than as a thing already there. Answered is
 * a plain hairline. Locked keeps the frame and dims the content, so the step
 * holds its place in the list while it waits for the one above it.
 */
@Composable
private fun StepRow(
    glyph: String,
    title: String,
    subtitle: String,
    modifier: Modifier = Modifier,
    action: String? = null,
    enabled: Boolean = true,
    onClick: () -> Unit,
) {
    val blank = action != null
    val dash = MbTheme.colors.hairlineStrong
    val hairline = MbTheme.colors.border
    Row(
        modifier
            .fillMaxWidth()
            .clip(MbTheme.shapes.field)
            .background(if (enabled) Color.Transparent else MbTheme.colors.surfaceAlt)
            .mbClickable(MbTheme.shapes.field, enabled = enabled, onClick = onClick)
            .drawBehind {
                drawRoundRect(
                    color = if (blank) dash else hairline,
                    style = Stroke(
                        width = if (blank) 1.4.dp.toPx() else 1.dp.toPx(),
                        pathEffect = if (blank) {
                            PathEffect.dashPathEffect(
                                floatArrayOf(6.dp.toPx(), 5.dp.toPx()),
                            )
                        } else {
                            null
                        },
                    ),
                    cornerRadius = CornerRadius(14.dp.toPx()),
                )
            }
            .padding(horizontal = 14.dp, vertical = 13.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Box(
            Modifier
                .size(38.dp)
                .clip(MbTheme.shapes.field)
                .background(MbTheme.colors.fill),
            contentAlignment = Alignment.Center,
        ) {
            MbIcon(
                glyph,
                size = 19.dp,
                tint = if (enabled) MbTheme.colors.inkSoft else MbTheme.colors.disabled,
            )
        }
        Column(Modifier.weight(1f)) {
            MbText(
                title,
                MbTheme.type.label,
                if (enabled) MbTheme.colors.ink else MbTheme.colors.disabled,
                maxLines = 1,
            )
            Spacer(Modifier.height(2.dp))
            MbText(
                subtitle,
                MbTheme.type.meta,
                if (enabled) MbTheme.colors.icon else MbTheme.colors.placeholder,
                maxLines = 1,
            )
        }
        if (action != null && enabled) {
            MbText(action, MbTheme.type.label, MbTheme.colors.accent, maxLines = 1)
        }
    }
}
