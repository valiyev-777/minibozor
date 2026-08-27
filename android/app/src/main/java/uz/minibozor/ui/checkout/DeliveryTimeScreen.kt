package uz.minibozor.ui.checkout

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import uz.minibozor.R
import uz.minibozor.core.design.MbText
import uz.minibozor.core.design.MbTheme
import uz.minibozor.core.design.component.MbBottomBar
import uz.minibozor.core.design.component.MbCard
import uz.minibozor.core.design.component.MbDivider
import uz.minibozor.core.design.component.MbPrimaryButton
import uz.minibozor.core.design.component.MbRadioRow
import uz.minibozor.core.design.component.MbScreen
import uz.minibozor.core.design.component.MbTopBar
import uz.minibozor.core.util.sum

/** Screen 21 — day chips across the top, time windows below. */
@Composable
fun DeliveryTimeScreen(
    viewModel: CheckoutViewModel,
    onBack: () -> Unit,
    onDone: () -> Unit,
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    var dayIndex by remember { mutableStateOf(0) }
    val days = state.slotDays

    MbScreen(
        topBar = { MbTopBar(stringResource(R.string.yetkazish_vaqti), onBack = onBack) },
        bottomBar = {
            MbBottomBar {
                MbPrimaryButton(stringResource(R.string.tasdiqlash), onDone, enabled = state.slotId != null)
            }
        },
    ) { padding ->
        LazyColumn(
            Modifier
                .fillMaxSize()
                .padding(padding),
            contentPadding = PaddingValues(12.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item {
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    days.forEachIndexed { index, day ->
                        val selected = index == dayIndex
                        Column(
                            Modifier
                                .weight(1f)
                                .clip(MbTheme.shapes.tile)
                                .background(
                                    if (selected) MbTheme.colors.ink else MbTheme.colors.surface
                                )
                                .border(
                                    width = if (selected) 1.6.dp else 1.dp,
                                    color = if (selected) MbTheme.colors.inverse
                                    else MbTheme.colors.border,
                                    shape = MbTheme.shapes.tile,
                                )
                                .clickable { dayIndex = index }
                                .padding(vertical = 12.dp),
                            horizontalAlignment = Alignment.CenterHorizontally,
                        ) {
                            MbText(
                                day.weekdayLabel,
                                MbTheme.type.micro,
                                if (selected) MbTheme.colors.onInverse.copy(alpha = 0.6f)
                                else MbTheme.colors.disabled,
                            )
                            Spacer(Modifier.height(4.dp))
                            MbText(
                                day.dayLabel,
                                MbTheme.type.title2,
                                if (selected) MbTheme.colors.onInverse
                                else MbTheme.colors.textSecondary,
                            )
                            MbText(
                                day.monthLabel,
                                MbTheme.type.micro,
                                if (selected) MbTheme.colors.onInverse.copy(alpha = 0.6f)
                                else MbTheme.colors.disabled,
                            )
                        }
                    }
                }
            }

            item {
                MbCard(padding = 6.dp) {
                    val slots = days.getOrNull(dayIndex)?.slots.orEmpty()
                    if (slots.isEmpty()) {
                        MbText(
                            stringResource(R.string.bu_kunga_bosh_oraliq_qolmadi),
                            MbTheme.type.bodySmall,
                            MbTheme.colors.icon,
                            modifier = Modifier.padding(16.dp),
                        )
                    }
                    slots.forEachIndexed { index, slot ->
                        MbRadioRow(
                            label = slot.label,
                            subtitle = slot.note.ifBlank { null },
                            selected = slot.id == state.slotId,
                            onSelect = { viewModel.selectSlot(slot.id) },
                            trailingLabel = if (slot.price == 0) stringResource(R.string.bepul) else "+${slot.price.sum()}",
                            trailingColor = if (slot.price == 0) MbTheme.colors.success
                            else MbTheme.colors.ink,
                            contentPadding = 10.dp,
                        )
                        if (index != slots.lastIndex) MbDivider()
                    }
                }
            }

            item {
                MbText(
                    stringResource(R.string.kuryer_yetkazishdan_30_daqiqa_oldin),
                    MbTheme.type.caption,
                    MbTheme.colors.textQuaternary,
                    modifier = Modifier.padding(horizontal = 6.dp),
                )
            }
        }
    }
}
