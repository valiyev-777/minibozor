package uz.minibozor.ui.settings

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import uz.minibozor.R
import uz.minibozor.core.design.MbText
import uz.minibozor.core.design.MbTheme
import uz.minibozor.core.design.component.MbBottomBar
import uz.minibozor.core.design.component.MbCodeField
import uz.minibozor.core.design.component.MbPrimaryButton
import uz.minibozor.core.design.component.MbScreen
import uz.minibozor.core.design.component.MbTopBar
import uz.minibozor.core.design.icon.MbIcon

/**
 * Screens 41–44 in one flow: current code, new code, confirmation and the
 * success state. [hasPin] decides whether the flow starts at step 0 or 1.
 */
@Composable
fun PinScreen(
    hasPin: Boolean,
    onBack: () -> Unit,
    onDone: () -> Unit,
    viewModel: PinViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    LaunchedEffect(hasPin) { viewModel.start(hasPin) }

    if (state.done) {
        PinDoneScreen(onDone)
        return
    }

    val (title, subtitle) = when (state.step) {
        0 -> stringResource(R.string.joriy_pin_kod) to stringResource(R.string.xavfsizlik_uchun_avval_joriy_kodni_kiriting)
        1 -> stringResource(R.string.yangi_pin_kod) to stringResource(R.string.pin_4_xonali_kod_oylab_toping)
        else -> stringResource(R.string.kodni_tasdiqlang) to stringResource(R.string.yangi_kodni_yana_bir_marta_kiriting)
    }
    val value = when (state.step) {
        0 -> state.current
        1 -> state.first
        else -> state.confirm
    }

    MbScreen(
        background = MbTheme.colors.surface,
        topBar = { MbTopBar("", onBack = onBack, background = MbTheme.colors.surface) },
    ) { padding ->
        Column(
            Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 26.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Spacer(Modifier.height(20.dp))
            MbText(title, MbTheme.type.title1, textAlign = TextAlign.Center)
            Spacer(Modifier.height(8.dp))
            MbText(
                subtitle,
                MbTheme.type.bodySmall,
                MbTheme.colors.textTertiary,
                textAlign = TextAlign.Center,
            )
            Spacer(Modifier.height(34.dp))
            MbCodeField(
                value = value,
                onValueChange = viewModel::onDigits,
                length = PinViewModel.LENGTH,
                masked = true,
                isError = state.error != null,
            )
            if (state.error != null) {
                Spacer(Modifier.height(14.dp))
                MbText(state.error!!, MbTheme.type.caption, MbTheme.colors.danger)
            }
            Spacer(Modifier.weight(1f))
            MbText(
                stringResource(R.string.kodni_hech_kimga_aytmang_mini_bozor),
                MbTheme.type.caption,
                MbTheme.colors.disabled,
                textAlign = TextAlign.Center,
                modifier = Modifier.padding(bottom = 30.dp),
            )
        }
    }
}

/** Screen 44 — PIN o'zgartirildi. */
@Composable
private fun PinDoneScreen(onDone: () -> Unit) {
    MbScreen(
        background = MbTheme.colors.surface,
        bottomBar = { MbBottomBar { MbPrimaryButton(stringResource(R.string.tayyor), onDone) } },
    ) { padding ->
        Column(
            Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 30.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Spacer(Modifier.height(70.dp))
            Box(
                Modifier
                    .size(96.dp)
                    .clip(CircleShape)
                    .background(MbTheme.colors.successBg),
                contentAlignment = Alignment.Center,
            ) {
                MbIcon("gear", size = 40.dp, tint = MbTheme.colors.success, strokeWidth = 1.6f)
            }
            Spacer(Modifier.height(22.dp))
            MbText(stringResource(R.string.pin_ozgartirildi), MbTheme.type.title1, textAlign = TextAlign.Center)
            Spacer(Modifier.height(8.dp))
            MbText(
                stringResource(R.string.endi_ilovaga_kirishda_yangi_kod_soraladi),
                MbTheme.type.bodySmall,
                MbTheme.colors.textTertiary,
                textAlign = TextAlign.Center,
            )
        }
    }
}
