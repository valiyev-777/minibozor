package uz.minibozor.ui.checkout

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.LifecycleResumeEffect
import androidx.lifecycle.compose.collectAsStateWithLifecycle
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
 * Choosing where an order goes: the saved addresses first, then the pick-up
 * points, with the form one step further in.
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

    // Coming back from the form should show what was just added.
    LifecycleResumeEffect(Unit) {
        viewModel.reloadAddresses()
        onPauseOrDispose {}
    }

    MbScreen(
        topBar = { MbTopBar("Yetkazish manzili", onBack = onBack) },
        bottomBar = {
            MbBottomBar {
                MbPrimaryButton(
                    text = "Tasdiqlash",
                    onClick = onBack,
                    enabled = state.addressId != null || state.pickupPointId != null,
                )
            }
        },
    ) { padding ->
        if (state.addresses.isEmpty() && state.pickupPoints.isEmpty()) {
            MbEmptyState(
                glyph = "pin",
                title = "Manzil yo'q",
                message = "Yetkazish uchun birinchi manzilingizni qo'shing.",
                actionLabel = "Manzil qo'shish",
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
            if (state.addresses.isNotEmpty()) {
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
                                modifier = Modifier.padding(horizontal = 10.dp),
                            )
                            if (index != state.addresses.lastIndex) MbDivider(inset = 42.dp)
                        }
                    }
                }
            }

            if (state.pickupPoints.isNotEmpty()) {
                item {
                    MbText(
                        "Yoki punktdan olib ketish",
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
                                    point.distanceKm?.let { "$it km" },
                                ).joinToString(" · "),
                                selected = state.pickupPointId == point.id,
                                onSelect = { viewModel.selectPickup(point.id) },
                                leading = { MbIcon("box", size = 18.dp) },
                                modifier = Modifier.padding(horizontal = 10.dp),
                            )
                            if (index != state.pickupPoints.lastIndex) MbDivider(inset = 42.dp)
                        }
                    }
                }
            }

            item {
                MbCard(padding = 6.dp) {
                    MbListRow(
                        label = "Yangi manzil qo'shish",
                        glyph = "pin",
                        tint = MbTheme.colors.accent,
                        onClick = onAddNew,
                        modifier = Modifier.padding(horizontal = 10.dp),
                    )
                }
            }
        }
    }
}
