package uz.minibozor.ui.checkout

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
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
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
import uz.minibozor.data.remote.dto.AddressRequest

private val PRESETS = listOf(
    Triple("Uy", "pin", "ASOSIY"),
    Triple("Ish", "box", "OFIS"),
    Triple("Boshqa", "star", null),
)

/** Screen 20 — Manzil qo'shish. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun AddressFormScreen(
    viewModel: CheckoutViewModel,
    onBack: () -> Unit,
    onSaved: () -> Unit,
) {
    var preset by remember { mutableStateOf(PRESETS.first()) }
    var line by remember { mutableStateOf("") }
    var floor by remember { mutableStateOf("") }
    var apartment by remember { mutableStateOf("") }
    var entranceCode by remember { mutableStateOf("") }
    var comment by remember { mutableStateOf("") }
    var isDefault by remember { mutableStateOf(false) }

    MbScreen(
        topBar = { MbTopBar("Manzil qo'shish", onBack = onBack) },
        bottomBar = {
            MbBottomBar {
                MbPrimaryButton(
                    text = "Saqlash",
                    enabled = line.isNotBlank(),
                    onClick = {
                        viewModel.createAddress(
                            AddressRequest(
                                title = preset.first,
                                icon = preset.second,
                                badge = preset.third,
                                line = line.trim(),
                                floor = floor.ifBlank { null },
                                apartment = apartment.ifBlank { null },
                                entranceCode = entranceCode.ifBlank { null },
                                comment = comment.ifBlank { null },
                                isDefault = isDefault,
                            ),
                            onDone = onSaved,
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
                SectionHeader("Manzil turi")
                Spacer(Modifier.height(12.dp))
                FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    PRESETS.forEach { option ->
                        MbChip(
                            label = option.first,
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
                    label = "Ko'cha va uy raqami",
                    placeholder = "Toshkent, Amir Temur shoh ko'chasi 108",
                )
                Spacer(Modifier.height(14.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    MbTextField(
                        value = floor,
                        onValueChange = { floor = it },
                        label = "Qavat",
                        placeholder = "12",
                        modifier = Modifier.weight(1f),
                    )
                    MbTextField(
                        value = apartment,
                        onValueChange = { apartment = it },
                        label = "Xona",
                        placeholder = "45",
                        modifier = Modifier.weight(1f),
                    )
                }
                Spacer(Modifier.height(14.dp))
                MbTextField(
                    value = entranceCode,
                    onValueChange = { entranceCode = it },
                    label = "Kirish kodi",
                    placeholder = "1245K",
                )
                Spacer(Modifier.height(14.dp))
                MbTextField(
                    value = comment,
                    onValueChange = { comment = it },
                    label = "Kuryerga izoh",
                    placeholder = "Domofon ishlamaydi, qo'ng'iroq qiling",
                    imeAction = ImeAction.Done,
                    singleLine = false,
                    minHeight = 80.dp,
                )
            }

            MbCard(padding = 6.dp) {
                MbToggleRow(
                    label = "Asosiy manzil",
                    subtitle = "Buyurtma berishda avtomatik tanlanadi",
                    checked = isDefault,
                    onCheckedChange = { isDefault = it },
                    glyph = "pin",
                    modifier = Modifier.padding(horizontal = 10.dp),
                )
            }
        }
    }
}
