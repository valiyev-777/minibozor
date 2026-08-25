package uz.minibozor.ui.profile

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import uz.minibozor.R
import uz.minibozor.core.design.MbText
import uz.minibozor.core.design.MbTheme
import uz.minibozor.core.design.component.MbDangerButton
import uz.minibozor.core.design.component.MbSecondaryButton

/** Screen 47 — Hisobdan chiqish, shown as a confirmation over the profile. */
@Composable
fun SignOutDialog(onDismiss: () -> Unit, onConfirm: () -> Unit) {
    Dialog(onDismissRequest = onDismiss) {
        Column(
            Modifier
                .fillMaxWidth()
                .clip(MbTheme.shapes.card)
                .background(MbTheme.colors.surface)
                .padding(24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            MbText(stringResource(R.string.hisobdan_chiqasizmi), MbTheme.type.title3, textAlign = TextAlign.Center)
            Spacer(Modifier.height(8.dp))
            MbText(
                stringResource(R.string.savat_va_sevimlilar_hisobingizda_saqlanadi),
                MbTheme.type.bodySmall,
                MbTheme.colors.textTertiary,
                textAlign = TextAlign.Center,
            )
            Spacer(Modifier.height(22.dp))
            MbDangerButton(stringResource(R.string.chiqish), onConfirm)
            Spacer(Modifier.height(10.dp))
            MbSecondaryButton(stringResource(R.string.bekor_qilish), onDismiss)
        }
    }
}
