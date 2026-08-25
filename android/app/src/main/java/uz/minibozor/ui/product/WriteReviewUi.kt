package uz.minibozor.ui.product

import androidx.compose.ui.res.stringArrayResource
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import uz.minibozor.R
import uz.minibozor.core.design.MbText
import uz.minibozor.core.design.MbTheme
import uz.minibozor.core.design.component.MbBottomBar
import uz.minibozor.core.design.component.MbCard
import uz.minibozor.core.design.component.MbChip
import uz.minibozor.core.design.component.MbPrimaryButton
import uz.minibozor.core.design.component.MbScreen
import uz.minibozor.core.design.component.MbTextField
import uz.minibozor.core.design.component.MbTopBar
import uz.minibozor.core.design.component.SectionHeader



/** Screen 16 — Sharh yozish. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun WriteReviewScreen(
    productId: Int,
    orderItemId: Int?,
    onBack: () -> Unit,
    onDone: () -> Unit,
    viewModel: WriteReviewViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()

    LaunchedEffect(state.done) { if (state.done) onDone() }

    MbScreen(
        topBar = { MbTopBar(stringResource(R.string.sharh_yozish), onBack = onBack) },
        bottomBar = {
            MbBottomBar {
                MbPrimaryButton(
                    text = stringResource(R.string.yuborish),
                    onClick = { viewModel.submit(productId, orderItemId) },
                    loading = state.submitting,
                    enabled = state.rating > 0,
                )
            }
        },
    ) { padding ->
        Column(
            Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState())
                .padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            MbCard {
                MbText(
                    stringResource(R.string.mahsulotni_qanday_baholaysiz),
                    MbTheme.type.title3,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.fillMaxWidth(),
                )
                Spacer(Modifier.height(16.dp))
                Row(
                    Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.Center,
                ) {
                    (1..5).forEach { star ->
                        MbText(
                            "★",
                            MbTheme.type.display,
                            if (star <= state.rating) MbTheme.colors.star else MbTheme.colors.divider,
                            modifier = Modifier
                                .clickable { viewModel.setRating(star) }
                                .padding(horizontal = 6.dp),
                        )
                    }
                }
                Spacer(Modifier.height(10.dp))
                MbText(
                    stringArrayResource(R.array.rating_words)
                        .getOrElse(state.rating) { "" },
                    MbTheme.type.label,
                    MbTheme.colors.textSecondary,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.fillMaxWidth(),
                )
            }

            if (state.tags.isNotEmpty()) {
                MbCard {
                    SectionHeader(stringResource(R.string.nimasi_yoqdi))
                    Spacer(Modifier.height(12.dp))
                    FlowRow(
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        state.tags.forEach { tag ->
                            MbChip(
                                label = tag,
                                selected = tag in state.selectedTags,
                                onClick = { viewModel.toggleTag(tag) },
                            )
                        }
                    }
                }
            }

            MbCard {
                SectionHeader(stringResource(R.string.fikringiz), "ixtiyoriy")
                Spacer(Modifier.height(12.dp))
                MbTextField(
                    value = state.text,
                    onValueChange = viewModel::setText,
                    placeholder = stringResource(R.string.sifati_olchami_yetkazish_haqida_yozing),
                    singleLine = false,
                    minHeight = 120.dp,
                )
                if (state.error != null) {
                    Spacer(Modifier.height(10.dp))
                    MbText(state.error!!, MbTheme.type.caption, MbTheme.colors.danger)
                }
            }

            MbText(
                stringResource(R.string.sharh_moderatsiyadan_otgach_e_lon_qilinadi),
                MbTheme.type.caption,
                MbTheme.colors.textQuaternary,
                textAlign = TextAlign.Center,
                modifier = Modifier.fillMaxWidth(),
            )
        }
    }
}
