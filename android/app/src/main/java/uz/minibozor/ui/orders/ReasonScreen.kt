package uz.minibozor.ui.orders

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import uz.minibozor.R
import uz.minibozor.core.design.MbText
import uz.minibozor.core.design.MbTheme
import uz.minibozor.core.design.component.MbBottomBar
import uz.minibozor.core.design.component.MbCard
import uz.minibozor.core.design.component.MbDangerButton
import uz.minibozor.core.design.component.MbDivider
import uz.minibozor.core.design.component.MbPrimaryButton
import uz.minibozor.core.design.component.MbRadioRow
import uz.minibozor.core.design.component.MbScreen
import uz.minibozor.core.design.component.MbTextField
import uz.minibozor.core.design.component.MbTopBar
import uz.minibozor.core.design.component.SectionHeader

/**
 * Screens 28 (cancel) and 29 (return). Both are "pick a reason, add a note,
 * confirm" — one composable, two configurations.
 */
@Composable
fun ReasonScreen(
    orderId: Int,
    isReturn: Boolean,
    onBack: () -> Unit,
    onDone: () -> Unit,
    viewModel: OrderDetailViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()

    LaunchedEffect(orderId, isReturn) {
        viewModel.load(orderId)
        if (isReturn) viewModel.loadReturnReasons() else viewModel.loadCancelReasons()
    }
    LaunchedEffect(state.finished) { if (state.finished) onDone() }

    val selected = state.reasons.firstOrNull { it.id == state.selectedReasonId }
    val needsComment = selected?.requiresComment == true
    val canSubmit = state.selectedReasonId != null && (!needsComment || state.comment.isNotBlank())

    MbScreen(
        topBar = {
            MbTopBar(
                title = if (isReturn) stringResource(R.string.qaytarish_arizasi) else stringResource(R.string.buyurtmani_bekor_qilish),
                onBack = onBack,
            )
        },
        bottomBar = {
            MbBottomBar {
                if (isReturn) {
                    MbPrimaryButton(
                        stringResource(R.string.ariza_yuborish),
                        viewModel::requestReturn,
                        enabled = canSubmit,
                        loading = state.submitting,
                    )
                } else {
                    MbDangerButton(
                        stringResource(R.string.bekor_qilishni_tasdiqlash),
                        viewModel::cancel,
                        loading = state.submitting,
                    )
                }
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
                MbText(
                    if (isReturn) {
                        stringResource(R.string.tovarni_nima_uchun_qaytarmoqchisiz)
                    } else {
                        stringResource(R.string.buyurtmani_nima_uchun_bekor_qilyapsiz)
                    },
                    MbTheme.type.title3,
                    modifier = Modifier.padding(horizontal = 6.dp, vertical = 4.dp),
                )
            }

            item {
                MbCard(padding = 6.dp) {
                    state.reasons.forEachIndexed { index, reason ->
                        MbRadioRow(
                            label = reason.label,
                            selected = reason.id == state.selectedReasonId,
                            onSelect = { viewModel.selectReason(reason.id) },
                            modifier = Modifier.padding(horizontal = 10.dp),
                        )
                        if (index != state.reasons.lastIndex) MbDivider()
                    }
                }
            }

            item {
                MbCard {
                    SectionHeader(stringResource(R.string.izoh), if (needsComment) "majburiy" else "ixtiyoriy")
                    Spacer(Modifier.height(12.dp))
                    MbTextField(
                        value = state.comment,
                        onValueChange = viewModel::setComment,
                        placeholder = stringResource(R.string.qisqacha_yozib_qoldiring),
                        singleLine = false,
                        minHeight = 100.dp,
                    )
                }
            }

            if (state.error != null) {
                item {
                    MbText(
                        state.error!!,
                        MbTheme.type.caption,
                        MbTheme.colors.danger,
                        modifier = Modifier.padding(horizontal = 6.dp),
                    )
                }
            }

            item {
                MbText(
                    if (isReturn) {
                        stringResource(R.string.ariza_korib_chiqilgach_sms_yuboramiz)
                    } else {
                        stringResource(R.string.tolangan_summa_1_3_ish_kunida_kartangizga)
                    },
                    MbTheme.type.caption,
                    MbTheme.colors.textQuaternary,
                    modifier = Modifier.padding(horizontal = 6.dp),
                )
            }
        }
    }
}
