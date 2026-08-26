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
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.LifecycleResumeEffect
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import uz.minibozor.R
import uz.minibozor.core.design.MbText
import uz.minibozor.core.design.MbTheme
import uz.minibozor.core.design.component.MbBottomBar
import uz.minibozor.core.design.component.MbCard
import uz.minibozor.core.design.component.MbDivider
import uz.minibozor.core.design.component.MbListRow
import uz.minibozor.core.design.component.MbPrimaryButton
import uz.minibozor.core.design.component.MbRadioRow
import uz.minibozor.core.design.component.MbScreen
import uz.minibozor.core.design.component.MbStatusPill
import uz.minibozor.core.design.component.MbTopBar
import uz.minibozor.core.design.icon.MbIcon

/** Screen 22 — saved cards plus cash on delivery. */
@Composable
fun PaymentMethodScreen(
    viewModel: CheckoutViewModel,
    onBack: () -> Unit,
    onAddCard: () -> Unit,
    onDone: () -> Unit,
) {
    val state by viewModel.state.collectAsStateWithLifecycle()

    LifecycleResumeEffect(Unit) {
        viewModel.reloadCards()
        onPauseOrDispose {}
    }

    MbScreen(
        topBar = { MbTopBar(stringResource(R.string.tolov_usuli), onBack = onBack) },
        bottomBar = {
            MbBottomBar {
                MbPrimaryButton(
                    stringResource(R.string.tanlash),
                    onDone,
                    enabled = state.paymentMethod == "cash" || state.cardId != null,
                )
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
                MbCard(padding = 6.dp) {
                    state.cards.forEachIndexed { index, card ->
                        val expired = card.status == "expired"
                        MbRadioRow(
                            label = stringResource(R.string.karta_niqob, card.last4),
                            subtitle = if (expired) stringResource(R.string.muddati_otgan) else card.brand,
                            selected = state.paymentMethod == "card" && state.cardId == card.id,
                            onSelect = { if (!expired) viewModel.selectCard(card.id) },
                            leading = {
                                Box(
                                    Modifier
                                        .size(46.dp, 30.dp)
                                        .clip(MbTheme.shapes.badge)
                                        .background(
                                            Brush.linearGradient(
                                                listOf(
                                                    MbTheme.colors.cardFrom,
                                                    if (expired) MbTheme.colors.disabled
                                                    else MbTheme.colors.accent,
                                                )
                                            )
                                        )
                                )
                            },
                            contentPadding = 10.dp,
                        )
                        if (index != state.cards.lastIndex) MbDivider(inset = 68.dp)
                    }
                    if (state.cards.isNotEmpty()) MbDivider(inset = 68.dp)
                    MbRadioRow(
                        label = stringResource(R.string.naqd_pul),
                        subtitle = stringResource(R.string.kuryerga_topshirishda),
                        selected = state.paymentMethod == "cash",
                        onSelect = viewModel::selectCash,
                        leading = {
                            Box(
                                Modifier
                                    .size(46.dp, 30.dp)
                                    .clip(MbTheme.shapes.badge)
                                    .background(MbTheme.colors.successBg),
                                contentAlignment = Alignment.Center,
                            ) {
                                MbIcon("basket", size = 16.dp, tint = MbTheme.colors.success)
                            }
                        },
                        contentPadding = 10.dp,
                    )
                }
            }

            item {
                MbCard(padding = 6.dp) {
                    MbListRow(
                        label = stringResource(R.string.yangi_karta_qoshish),
                        glyph = "card",
                        subtitle = stringResource(R.string.humo_uzcard_visa),
                        onClick = onAddCard,
                        tint = MbTheme.colors.accent,
                        contentPadding = 10.dp,
                    )
                }
            }

            item {
                Row(
                    Modifier.padding(horizontal = 6.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    MbIcon("gear", size = 16.dp, tint = MbTheme.colors.icon)
                    MbText(
                        stringResource(R.string.karta_ma_lumotlari_tolov_provayderi),
                        MbTheme.type.caption,
                        MbTheme.colors.textQuaternary,
                    )
                }
            }
        }
    }
}
