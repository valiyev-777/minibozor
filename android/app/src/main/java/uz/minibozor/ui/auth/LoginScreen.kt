package uz.minibozor.ui.auth

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.OffsetMapping
import androidx.compose.ui.text.input.TransformedText
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import uz.minibozor.R
import uz.minibozor.core.design.MbText
import uz.minibozor.core.design.MbTheme
import uz.minibozor.core.design.component.MbPrimaryButton
import uz.minibozor.core.design.component.MbScreen
import uz.minibozor.ui.onboarding.BrandMark

/**
 * Screen 05. Phone entry with a fixed +998 prefix — the field only ever holds
 * the nine national digits, which is also what [AuthViewModel] validates.
 */
@Composable
fun LoginScreen(
    onCodeSent: (String) -> Unit,
    onOpenTerms: () -> Unit,
    viewModel: AuthViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()

    LaunchedEffect(state.codeSent) {
        if (state.codeSent) onCodeSent(state.phoneDigits)
    }

    MbScreen(background = MbTheme.colors.surface) { padding ->
        Column(
            Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 26.dp),
        ) {
            Spacer(Modifier.height(28.dp))
            BrandMark(size = 46.dp)
            Spacer(Modifier.height(20.dp))
            MbText("Mini Bozor", MbTheme.type.display)
            Spacer(Modifier.height(8.dp))
            MbText(
                stringResource(R.string.telefon_raqamingizni_kiriting_sms_kod),
                MbTheme.type.bodySmall,
                MbTheme.colors.textTertiary,
            )

            Spacer(Modifier.height(28.dp))
            PhoneField(
                digits = state.phoneDigits,
                onChange = viewModel::onPhoneChange,
                error = state.error,
            )

            Spacer(Modifier.height(18.dp))
            MbPrimaryButton(
                text = stringResource(R.string.davom_etish),
                onClick = viewModel::sendCode,
                enabled = state.phoneValid,
                loading = state.sending,
            )

            Spacer(Modifier.height(14.dp))
            MbText(
                stringResource(R.string.menda_referal_kod_bor),
                MbTheme.type.label,
                MbTheme.colors.accent,
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { },
                textAlign = TextAlign.Center,
            )

            Spacer(Modifier.height(28.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Divider(Modifier.weight(1f))
                MbText(
                    stringResource(R.string.yoki_tezkor_kirish),
                    MbTheme.type.caption,
                    MbTheme.colors.textQuaternary,
                )
                Divider(Modifier.weight(1f))
            }

            Spacer(Modifier.height(18.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                listOf(stringResource(R.string.apple), stringResource(R.string.google), stringResource(R.string.oneid)).forEach { provider ->
                    SocialButton(provider, Modifier.weight(1f))
                }
            }

            Spacer(Modifier.weight(1f))
            Spacer(Modifier.height(32.dp))
            Row(
                Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.Center,
            ) {
                MbText(stringResource(R.string.kirish_orqali), MbTheme.type.caption, MbTheme.colors.textQuaternary)
                MbText(
                    stringResource(R.string.ommaviy_oferta),
                    MbTheme.type.caption,
                    MbTheme.colors.accent,
                    modifier = Modifier
                        .clip(MbTheme.shapes.chip)
                        .clickable(onClick = onOpenTerms)
                        .padding(horizontal = 6.dp, vertical = 4.dp),
                )
                MbText(stringResource(R.string.shartlariga_rozilik_bildirasiz), MbTheme.type.caption, MbTheme.colors.textQuaternary)
            }
            Spacer(Modifier.height(24.dp))
        }
    }
}

@Composable
private fun PhoneField(digits: String, onChange: (String) -> Unit, error: String?) {
    Column {
        Row(
            Modifier
                .fillMaxWidth()
                .height(56.dp)
                .clip(MbTheme.shapes.field)
                .background(MbTheme.colors.fill)
                .padding(horizontal = 16.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            MbText("+998", MbTheme.type.title3, MbTheme.colors.ink)
            Spacer(Modifier.width(12.dp))
            Box(Modifier.weight(1f)) {
                if (digits.isEmpty()) {
                    MbText("-- --- -- --", MbTheme.type.title3, MbTheme.colors.disabled)
                }
                BasicTextField(
                    value = digits,
                    onValueChange = onChange,
                    singleLine = true,
                    textStyle = MbTheme.type.title3.copy(color = MbTheme.colors.ink),
                    cursorBrush = SolidColor(MbTheme.colors.accent),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone),
                    visualTransformation = PhoneMask,
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        }
        if (error != null) {
            Spacer(Modifier.height(8.dp))
            MbText(error, MbTheme.type.caption, MbTheme.colors.danger)
        }
    }
}

@Composable
private fun SocialButton(label: String, modifier: Modifier = Modifier) {
    Box(
        modifier
            .height(46.dp)
            .clip(MbTheme.shapes.field)
            .background(MbTheme.colors.fill)
            .clickable { },
        contentAlignment = Alignment.Center,
    ) {
        MbText(label, MbTheme.type.label, MbTheme.colors.inkSoft)
    }
}

@Composable
private fun Divider(modifier: Modifier = Modifier) {
    Box(
        modifier
            .height(1.dp)
            .background(MbTheme.colors.border)
    )
}

/** `901234567` → `90 123 45 67`. */
private val PhoneMask = VisualTransformation { text ->
    val digits = text.text
    val out = buildString {
        digits.forEachIndexed { index, ch ->
            if (index == 2 || index == 5 || index == 7) append(' ')
            append(ch)
        }
    }
    val offsets = object : OffsetMapping {
        override fun originalToTransformed(offset: Int): Int = when {
            offset <= 2 -> offset
            offset <= 5 -> offset + 1
            offset <= 7 -> offset + 2
            else -> offset + 3
        }

        override fun transformedToOriginal(offset: Int): Int = when {
            offset <= 2 -> offset
            offset <= 6 -> offset - 1
            offset <= 9 -> offset - 2
            else -> offset - 3
        }.coerceIn(0, digits.length)
    }
    TransformedText(AnnotatedString(out), offsets)
}
