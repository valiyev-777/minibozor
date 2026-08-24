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
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
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
        0 -> "Joriy PIN kod" to "Xavfsizlik uchun avval joriy kodni kiriting"
        1 -> "Yangi PIN kod" to "4 xonali kod o'ylab toping"
        else -> "Kodni tasdiqlang" to "Yangi kodni yana bir marta kiriting"
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
                "Kodni hech kimga aytmang. Mini Bozor xodimlari PIN so'ramaydi.",
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
        bottomBar = { MbBottomBar { MbPrimaryButton("Tayyor", onDone) } },
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
            MbText("PIN o'zgartirildi", MbTheme.type.title1, textAlign = TextAlign.Center)
            Spacer(Modifier.height(8.dp))
            MbText(
                "Endi ilovaga kirishda yangi kod so'raladi.",
                MbTheme.type.bodySmall,
                MbTheme.colors.textTertiary,
                textAlign = TextAlign.Center,
            )
        }
    }
}
