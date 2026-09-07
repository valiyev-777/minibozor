package uz.minibozor.ui.checkout

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.LifecycleResumeEffect
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import uz.minibozor.R
import uz.minibozor.core.design.MbText
import uz.minibozor.core.design.MbTheme
import uz.minibozor.core.design.component.MbBottomBar
import uz.minibozor.core.design.component.MbCard
import uz.minibozor.core.design.component.MbDivider
import uz.minibozor.core.design.component.MbEmptyState
import uz.minibozor.core.design.component.MbListRow
import uz.minibozor.core.design.component.MbPrimaryButton
import uz.minibozor.core.design.component.MbRadioRow
import uz.minibozor.core.design.component.MbScreen
import uz.minibozor.core.design.component.MbTopBar
import uz.minibozor.core.design.icon.MbIcon

/**
 * Choosing where an order goes: one question at a time.
 *
 * It used to ask both at once — every saved address, and under them every
 * pick-up point in the city. So a customer who had chosen "Kuryer" and pressed
 * "Manzil qo'shish" was handed a page of counters to collect from, and picking
 * one silently turned their order into a collection: the courier tile above
 * unselected itself, the delivery time they had chosen was dropped, and nothing
 * on the screen had asked whether that was what they wanted.
 *
 * The delivery method is chosen on the checkout screen and this screen answers
 * only for the one that was chosen. The other way is still available, where it
 * belongs — one card up, on the two tiles that are about exactly that.
 *
 * Tapping "manzil" during checkout used to open the *form* directly, which
 * meant anyone with saved addresses had to type one again to get past it.
 */
@Composable
fun AddressPickerScreen(
    viewModel: CheckoutViewModel,
    onBack: () -> Unit,
    onAddNew: () -> Unit,
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val courier = state.delivery == DeliveryMethod.Courier

    // Coming back from the form should show what was just added.
    LifecycleResumeEffect(Unit) {
        viewModel.reloadAddresses()
        onPauseOrDispose {}
    }

    MbScreen(
        topBar = {
            MbTopBar(
                stringResource(
                    if (courier) R.string.yetkazish_manzili else R.string.punkt_tanlash
                ),
                onBack = onBack,
            )
        },
        bottomBar = {
            MbBottomBar {
                MbPrimaryButton(
                    text = stringResource(R.string.tasdiqlash),
                    onClick = onBack,
                    enabled = if (courier) {
                        state.addressId != null
                    } else {
                        state.pickupPointId != null
                    },
                )
            }
        },
    ) { padding ->
        if (courier && state.addresses.isEmpty()) {
            MbEmptyState(
                glyph = "pin",
                title = stringResource(R.string.manzil_yoq),
                message = stringResource(R.string.yetkazish_uchun_birinchi_manzilingizni),
                actionLabel = stringResource(R.string.manzil_qoshish),
                onAction = onAddNew,
                modifier = Modifier.padding(padding),
            )
            return@MbScreen
        }

        LazyColumn(
            Modifier
                .fillMaxSize()
                .padding(padding),
            contentPadding = PaddingValues(12.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            if (courier && state.addresses.isNotEmpty()) {
                item {
                    MbCard(padding = 6.dp) {
                        state.addresses.forEachIndexed { index, address ->
                            MbRadioRow(
                                label = address.title,
                                subtitle = listOf(address.line, address.meta)
                                    .filter { it.isNotBlank() }
                                    .joinToString(" · "),
                                selected = state.addressId == address.id,
                                onSelect = { viewModel.selectAddress(address.id) },
                                leading = { MbIcon(address.icon, size = 18.dp) },
                                contentPadding = 10.dp,
                            )
                            if (index != state.addresses.lastIndex) MbDivider(inset = 42.dp)
                        }
                    }
                }
            }

            if (!courier && state.pickupPoints.isNotEmpty()) {
                item {
                    MbText(
                        stringResource(R.string.ozingizga_qulay_punktni_tanlang),
                        MbTheme.type.captionBold,
                        MbTheme.colors.textSecondary,
                        modifier = Modifier.padding(start = 6.dp),
                    )
                }
                item {
                    MbCard(padding = 6.dp) {
                        state.pickupPoints.forEachIndexed { index, point ->
                            MbRadioRow(
                                label = point.name,
                                subtitle = listOfNotNull(
                                    point.address.ifBlank { null },
                                    point.hours.ifBlank { null },
                                    point.distanceKm?.let { stringResource(R.string.n_km, it) },
                                ).joinToString(" · "),
                                selected = state.pickupPointId == point.id,
                                onSelect = { viewModel.selectPickup(point.id) },
                                leading = { MbIcon("box", size = 18.dp) },
                                contentPadding = 10.dp,
                            )
                            if (index != state.pickupPoints.lastIndex) MbDivider(inset = 42.dp)
                        }
                    }
                }
            }

            // Only where a new one can be added: a customer cannot open a
            // pick-up counter.
            if (courier) {
                item {
                    MbCard(padding = 6.dp) {
                        MbListRow(
                            label = stringResource(R.string.yangi_manzil_qoshish),
                            glyph = "pin",
                            tint = MbTheme.colors.accent,
                            onClick = onAddNew,
                            contentPadding = 10.dp,
                        )
                    }
                }
            }
        }
    }
}
