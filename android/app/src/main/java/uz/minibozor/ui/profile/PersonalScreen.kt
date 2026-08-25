package uz.minibozor.ui.profile

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
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
import uz.minibozor.core.util.formatPhone

/** Screen 31 — Shaxsiy ma'lumotlar. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun PersonalScreen(
    onBack: () -> Unit,
    viewModel: ProfileViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val user = state.overview?.user

    var fullName by remember(user?.id) { mutableStateOf(user?.fullName.orEmpty()) }
    var email by remember(user?.id) { mutableStateOf(user?.email.orEmpty()) }
    var birthDate by remember(user?.id) { mutableStateOf(user?.birthDate.orEmpty()) }
    var gender by remember(user?.id) { mutableStateOf(user?.gender.orEmpty()) }

    LaunchedEffect(state.saved) { if (state.saved) onBack() }

    MbScreen(
        topBar = { MbTopBar(stringResource(R.string.shaxsiy_ma_lumotlar), onBack = onBack) },
        bottomBar = {
            MbBottomBar {
                MbPrimaryButton(
                    text = stringResource(R.string.saqlash),
                    onClick = {
                        viewModel.save(
                            fullName = fullName,
                            email = email,
                            birthDate = birthDate.ifBlank { null },
                            gender = gender.ifBlank { null },
                        )
                    },
                    loading = state.saving,
                    enabled = fullName.isNotBlank(),
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
                MbTextField(
                    value = fullName,
                    onValueChange = { fullName = it },
                    label = stringResource(R.string.ism_va_familiya),
                    placeholder = stringResource(R.string.aziz_toshmatov_2),
                )
                Spacer(Modifier.height(14.dp))
                MbTextField(
                    value = user?.phone?.formatPhone().orEmpty(),
                    onValueChange = {},
                    label = stringResource(R.string.telefon),
                    trailing = {
                        MbText(stringResource(R.string.ozgartirib_bolmaydi), MbTheme.type.micro, MbTheme.colors.disabled)
                    },
                )
                Spacer(Modifier.height(14.dp))
                MbTextField(
                    value = email,
                    onValueChange = { email = it },
                    label = stringResource(R.string.email),
                    placeholder = "siz@example.uz",
                    keyboardType = KeyboardType.Email,
                )
                Spacer(Modifier.height(14.dp))
                MbTextField(
                    value = birthDate,
                    onValueChange = { birthDate = it },
                    label = stringResource(R.string.tugilgan_sana),
                    placeholder = "1994-05-12",
                    keyboardType = KeyboardType.Number,
                    imeAction = ImeAction.Done,
                )
            }

            MbCard {
                SectionHeader(stringResource(R.string.jins))
                Spacer(Modifier.height(12.dp))
                FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    listOf("erkak", "ayol").forEach { option ->
                        MbChip(
                            label = option.replaceFirstChar(Char::uppercase),
                            selected = gender == option,
                            onClick = { gender = if (gender == option) "" else option },
                        )
                    }
                }
            }

            if (state.error != null) {
                MbText(
                    state.error!!,
                    MbTheme.type.caption,
                    MbTheme.colors.danger,
                    modifier = Modifier.padding(horizontal = 6.dp),
                )
            }
        }
    }
}
