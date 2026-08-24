package uz.minibozor.ui.auth

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import uz.minibozor.core.design.MbText
import uz.minibozor.core.design.MbTheme
import uz.minibozor.core.design.component.MbCodeField
import uz.minibozor.core.design.component.MbPrimaryButton
import uz.minibozor.core.design.component.MbScreen
import uz.minibozor.core.design.component.MbTopBar
import uz.minibozor.core.util.formatPhone

/**
 * Screen 06. The code auto-submits once six digits are in, which is what the
 * design's "Kod avtomatik o'qiladi" note promises.
 */
@Composable
fun OtpScreen(
    phoneDigits: String,
    onBack: () -> Unit,
    onSignedIn: (isNewUser: Boolean) -> Unit,
    viewModel: AuthViewModel,
) {
    val state by viewModel.state.collectAsStateWithLifecycle()

    LaunchedEffect(state.signedIn) {
        if (state.signedIn) {
            viewModel.consumeSignIn()
            onSignedIn(state.isNewUser)
        }
    }

    MbScreen(
        background = MbTheme.colors.surface,
        topBar = { MbTopBar(title = "", onBack = onBack, background = MbTheme.colors.surface) },
    ) { padding ->
        Column(
            Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 26.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Spacer(Modifier.height(12.dp))
            MbText("Tasdiqlash kodi", MbTheme.type.display, textAlign = TextAlign.Center)
            Spacer(Modifier.height(10.dp))
            MbText(
                "${phoneDigits.formatPhone()} raqamiga " +
                    "${AuthState.CODE_LENGTH} xonali kod yubordik",
                MbTheme.type.bodySmall,
                MbTheme.colors.textTertiary,
                textAlign = TextAlign.Center,
            )

            Spacer(Modifier.height(30.dp))
            MbCodeField(
                value = state.code,
                onValueChange = viewModel::onCodeChange,
                length = AuthState.CODE_LENGTH,
                isError = state.error != null,
            )

            if (state.error != null) {
                Spacer(Modifier.height(12.dp))
                MbText(state.error!!, MbTheme.type.caption, MbTheme.colors.danger)
            }

            if (state.devCode != null) {
                Spacer(Modifier.height(12.dp))
                MbText(
                    "Dev rejim: kod ${state.devCode}",
                    MbTheme.type.caption,
                    MbTheme.colors.textQuaternary,
                )
            }

            Spacer(Modifier.height(20.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                if (state.canResend) {
                    MbText(
                        "Kodni qayta yuborish",
                        MbTheme.type.label,
                        MbTheme.colors.accent,
                        modifier = Modifier.clickable { viewModel.sendCode() },
                    )
                } else {
                    MbText(
                        "Kodni qayta yuborish — ",
                        MbTheme.type.caption,
                        MbTheme.colors.textQuaternary,
                    )
                    MbText(state.secondsLeft.asClock(), MbTheme.type.label, MbTheme.colors.ink)
                }
            }

            Spacer(Modifier.height(24.dp))
            MbPrimaryButton(
                text = "Tasdiqlash",
                onClick = viewModel::verify,
                enabled = state.codeValid,
                loading = state.verifying,
            )

            Spacer(Modifier.weight(1f))
            Column(
                Modifier.fillMaxWidth(),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                MbText(
                    "Kod avtomatik o'qiladi — SMS kelishi bilan davom etamiz",
                    MbTheme.type.caption,
                    MbTheme.colors.textQuaternary,
                    textAlign = TextAlign.Center,
                )
                MbText(
                    "Kod kelmadimi? 1150 raqamiga qo'ng'iroq qiling — bepul",
                    MbTheme.type.caption,
                    MbTheme.colors.disabled,
                    textAlign = TextAlign.Center,
                )
            }
            Spacer(Modifier.height(28.dp))
        }
    }
}

private fun Int.asClock(): String = "%02d:%02d".format(this / 60, this % 60)
