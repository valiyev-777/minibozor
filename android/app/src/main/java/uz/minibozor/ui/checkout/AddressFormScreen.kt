package uz.minibozor.ui.checkout

import androidx.annotation.StringRes
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import uz.minibozor.R
import uz.minibozor.core.design.MbTheme
import uz.minibozor.core.design.component.MbBottomBar
import uz.minibozor.core.design.component.MbCard
import uz.minibozor.core.design.component.MbChip
import uz.minibozor.core.design.component.MbPrimaryButton
import uz.minibozor.core.design.component.MbScreen
import uz.minibozor.core.design.component.MbTextField
import uz.minibozor.core.design.component.MbToggleRow
import uz.minibozor.core.design.component.MbTopBar
import uz.minibozor.core.design.component.SectionHeader
import uz.minibozor.core.util.AppStrings
import uz.minibozor.data.remote.dto.AddressRequest

/**
 * The quick-fill chips. The title is stored on the address, so it is written in
 * whichever language the user was using when they saved it — same as anything
 * else they type into the form.
 */
private data class AddressPreset(
    @StringRes val titleRes: Int,
    val glyph: String,
    @StringRes val badgeRes: Int?,
)

private val PRESETS = listOf(
    AddressPreset(R.string.preset_uy, "pin", R.string.preset_badge_asosiy),
    AddressPreset(R.string.preset_ish, "box", R.string.preset_badge_ofis),
    AddressPreset(R.string.preset_boshqa, "star", null),
)

/** Screen 20 — Manzil qo'shish. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun AddressFormScreen(
    onBack: () -> Unit,
    onSaved: () -> Unit,
    viewModel: AddressFormViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    LaunchedEffect(state.savedId) { if (state.savedId != null) onSaved() }

    var preset by remember { mutableStateOf(PRESETS.first()) }
    var line by remember { mutableStateOf("") }
    var floor by remember { mutableStateOf("") }
    var apartment by remember { mutableStateOf("") }
    var entranceCode by remember { mutableStateOf("") }
    var comment by remember { mutableStateOf("") }
    var isDefault by remember { mutableStateOf(false) }

    MbScreen(
        topBar = { MbTopBar(stringResource(R.string.manzil_qoshish), onBack = onBack) },
        bottomBar = {
            MbBottomBar {
                MbPrimaryButton(
                    text = stringResource(R.string.saqlash),
                    enabled = line.isNotBlank(),
                    loading = state.saving,
                    onClick = {
                        viewModel.save(
                            AddressRequest(
                                // Resolved here rather than read from the chip
                                // so the saved title matches the language the
                                // user is actually typing in.
                                title = AppStrings[preset.titleRes],
                                icon = preset.glyph,
                                badge = preset.badgeRes?.let { AppStrings[it] },
                                line = line.trim(),
                                floor = floor.ifBlank { null },
                                apartment = apartment.ifBlank { null },
                                entranceCode = entranceCode.ifBlank { null },
                                comment = comment.ifBlank { null },
                                isDefault = isDefault,
                            )
                        )
                    },
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
                SectionHeader(stringResource(R.string.manzil_turi))
                Spacer(Modifier.height(12.dp))
                FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    PRESETS.forEach { option ->
                        MbChip(
                            label = stringResource(option.titleRes),
                            selected = option == preset,
                            onClick = { preset = option },
                        )
                    }
                }
            }

            MbCard {
                MbTextField(
                    value = line,
                    onValueChange = { line = it },
                    label = stringResource(R.string.kocha_va_uy_raqami),
                    placeholder = stringResource(R.string.toshkent_amir_temur_shoh_kochasi_108),
                )
                Spacer(Modifier.height(14.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    MbTextField(
                        value = floor,
                        onValueChange = { floor = it },
                        label = stringResource(R.string.qavat),
                        placeholder = "12",
                        modifier = Modifier.weight(1f),
                    )
                    MbTextField(
                        value = apartment,
                        onValueChange = { apartment = it },
                        label = stringResource(R.string.xona),
                        placeholder = "45",
                        modifier = Modifier.weight(1f),
                    )
                }
                Spacer(Modifier.height(14.dp))
                MbTextField(
                    value = entranceCode,
                    onValueChange = { entranceCode = it },
                    label = stringResource(R.string.kirish_kodi),
                    placeholder = "1245K",
                )
                Spacer(Modifier.height(14.dp))
                MbTextField(
                    value = comment,
                    onValueChange = { comment = it },
                    label = stringResource(R.string.kuryerga_izoh),
                    placeholder = stringResource(R.string.domofon_ishlamaydi_qongiroq_qiling),
                    imeAction = ImeAction.Done,
                    singleLine = false,
                    minHeight = 80.dp,
                )
            }

            if (state.error != null) {
                uz.minibozor.core.design.MbText(
                    state.error!!,
                    uz.minibozor.core.design.MbTheme.type.caption,
                    uz.minibozor.core.design.MbTheme.colors.danger,
                    modifier = Modifier.padding(horizontal = 6.dp),
                )
            }

            MbCard(padding = 6.dp) {
                MbToggleRow(
                    label = stringResource(R.string.asosiy_manzil),
                    subtitle = stringResource(R.string.buyurtma_berishda_avtomatik_tanlanadi),
                    checked = isDefault,
                    onCheckedChange = { isDefault = it },
                    glyph = "pin",
                    contentPadding = 10.dp,
                )
            }
        }
    }
}
