package uz.minibozor.ui.profile

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
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
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.OffsetMapping
import androidx.compose.ui.text.input.TransformedText
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import uz.minibozor.core.design.MbText
import uz.minibozor.core.design.MbTheme
import uz.minibozor.core.design.component.MbBottomBar
import uz.minibozor.core.design.component.MbCard
import uz.minibozor.core.design.component.MbPrimaryButton
import uz.minibozor.core.design.component.MbScreen
import uz.minibozor.core.design.component.MbStatusPill
import uz.minibozor.core.design.component.MbTextField
import uz.minibozor.core.design.component.MbToggleRow
import uz.minibozor.core.design.component.MbTopBar
import uz.minibozor.core.design.icon.MbIcon
import uz.minibozor.core.util.CardBrand

/**
 * Screen 32 — "Yangi karta qo'shish".
 *
 * A live preview of the card above the form, the same gradient tile the saved
 * cards use. Only the brand, last four digits and expiry are sent — see
 * [AddCardViewModel].
 */
@Composable
fun AddCardScreen(
    onBack: () -> Unit,
    onSaved: () -> Unit,
    viewModel: AddCardViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()

    LaunchedEffect(state.done) { if (state.done) onSaved() }

    MbScreen(
        topBar = { MbTopBar("Karta qo'shish", onBack = onBack) },
        bottomBar = {
            MbBottomBar {
                MbPrimaryButton(
                    text = "Kartani saqlash",
                    onClick = viewModel::save,
                    enabled = state.canSave,
                    loading = state.saving,
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
            CardPreview(state)

            val numberError = if (state.numberComplete && !state.numberValid) {
                "Karta raqami noto'g'ri"
            } else null

            MbCard {
                MbTextField(
                    value = state.number,
                    onValueChange = viewModel::onNumberChange,
                    label = "Karta raqami",
                    placeholder = "8600 0000 0000 0000",
                    keyboardType = KeyboardType.NumberPassword,
                    leadingGlyph = "card",
                    visualTransformation = CardNumberMask,
                    error = numberError,
                )
                Spacer(Modifier.height(14.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    MbTextField(
                        value = state.expiry,
                        onValueChange = viewModel::onExpiryChange,
                        label = "Amal qilish muddati",
                        placeholder = "MM/YY",
                        keyboardType = KeyboardType.NumberPassword,
                        visualTransformation = ExpiryMask,
                        modifier = Modifier.weight(1f),
                    )
                    MbTextField(
                        value = state.brand.label,
                        onValueChange = {},
                        label = "To'lov tizimi",
                        readOnly = true,
                        modifier = Modifier.weight(1f),
                    )
                }
                Spacer(Modifier.height(14.dp))
                MbTextField(
                    value = state.holder,
                    onValueChange = viewModel::onHolderChange,
                    label = "Karta egasi",
                    placeholder = "AZIZ TOSHMATOV",
                    imeAction = ImeAction.Done,
                )
            }

            MbCard(padding = 6.dp) {
                MbToggleRow(
                    label = "Asosiy karta",
                    subtitle = "Buyurtma berishda avtomatik tanlanadi",
                    glyph = "card",
                    checked = state.makeDefault,
                    onCheckedChange = viewModel::onDefaultChange,
                    modifier = Modifier.padding(horizontal = 10.dp),
                )
            }

            if (state.error != null) {
                MbText(
                    state.error!!,
                    MbTheme.type.caption,
                    MbTheme.colors.danger,
                    modifier = Modifier.padding(horizontal = 6.dp),
                )
            }

            Row(
                Modifier.padding(horizontal = 6.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                MbIcon("gear", size = 16.dp, tint = MbTheme.colors.icon)
                MbText(
                    "Karta raqami qurilmadan chiqmaydi — serverda faqat oxirgi " +
                        "4 raqam va muddati saqlanadi.",
                    MbTheme.type.caption,
                    MbTheme.colors.textQuaternary,
                )
            }
        }
    }
}

@Composable
private fun CardPreview(state: CardFormState) {
    val digits = state.number.padEnd(16, '•').take(16)
    val masked = buildString {
        digits.forEachIndexed { index, ch ->
            if (index > 0 && index % 4 == 0) append("  ")
            append(if (index < 12 && ch != '•') '•' else ch)
        }
    }

    Column(
        Modifier
            .fillMaxWidth()
            .height(180.dp)
            .clip(MbTheme.shapes.card)
            .background(
                Brush.linearGradient(listOf(MbTheme.colors.cardFrom, MbTheme.colors.accent))
            )
            .padding(20.dp)
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            MbText(
                if (state.brand == CardBrand.UNKNOWN) "Yangi karta" else state.brand.label,
                MbTheme.type.label,
                Color.White,
            )
            Spacer(Modifier.weight(1f))
            if (state.makeDefault) {
                MbStatusPill("ASOSIY", Color.White.copy(alpha = 0.2f), Color.White)
            }
        }
        Spacer(Modifier.weight(1f))
        MbText(masked, MbTheme.type.title3, Color.White)
        Spacer(Modifier.height(10.dp))
        Row {
            MbText(
                state.holder.ifBlank { "KARTA EGASI" },
                MbTheme.type.caption,
                Color.White.copy(alpha = 0.75f),
            )
            Spacer(Modifier.weight(1f))
            MbText(
                if (state.expiry.length == 4) {
                    "${state.expiry.take(2)}/${state.expiry.drop(2)}"
                } else "MM/YY",
                MbTheme.type.caption,
                Color.White.copy(alpha = 0.75f),
            )
        }
    }
}

/** `8600123456789012` → `8600 1234 5678 9012`. */
private val CardNumberMask = VisualTransformation { text ->
    val digits = text.text
    val out = buildString {
        digits.forEachIndexed { index, ch ->
            if (index > 0 && index % 4 == 0) append(' ')
            append(ch)
        }
    }
    val offsets = object : OffsetMapping {
        override fun originalToTransformed(offset: Int): Int =
            offset + ((offset - 1).coerceAtLeast(0) / 4)

        override fun transformedToOriginal(offset: Int): Int =
            (offset - offset / 5).coerceIn(0, digits.length)
    }
    TransformedText(AnnotatedString(out), offsets)
}

/** `1229` → `12/29`. */
private val ExpiryMask = VisualTransformation { text ->
    val digits = text.text
    val out = if (digits.length > 2) "${digits.take(2)}/${digits.drop(2)}" else digits
    val offsets = object : OffsetMapping {
        override fun originalToTransformed(offset: Int): Int = if (offset <= 2) offset else offset + 1
        override fun transformedToOriginal(offset: Int): Int =
            (if (offset <= 2) offset else offset - 1).coerceIn(0, digits.length)
    }
    TransformedText(AnnotatedString(out), offsets)
}
