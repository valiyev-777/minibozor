package uz.minibozor.core.design.component

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import uz.minibozor.R
import uz.minibozor.core.design.MbText
import uz.minibozor.core.design.MbTheme
import uz.minibozor.core.design.icon.MbIcon

/** Labelled text field, matching the "Manzil qo'shish" and profile forms. */
@Composable
fun MbTextField(
    value: String,
    onValueChange: (String) -> Unit,
    label: String? = null,
    placeholder: String = "",
    modifier: Modifier = Modifier,
    keyboardType: KeyboardType = KeyboardType.Text,
    imeAction: ImeAction = ImeAction.Next,
    singleLine: Boolean = true,
    minHeight: Dp = 48.dp,
    leadingGlyph: String? = null,
    trailing: @Composable (() -> Unit)? = null,
    error: String? = null,
    readOnly: Boolean = false,
    visualTransformation: VisualTransformation = VisualTransformation.None,
) {
    Column(modifier) {
        if (label != null) {
            MbText(label, MbTheme.type.caption, MbTheme.colors.textQuaternary)
            Spacer(Modifier.height(6.dp))
        }
        Row(
            Modifier
                .fillMaxWidth()
                .heightIn(min = minHeight)
                .clip(MbTheme.shapes.field)
                .background(MbTheme.colors.fill)
                .border(
                    width = if (error != null) 1.5.dp else 0.dp,
                    color = if (error != null) MbTheme.colors.danger else Color.Transparent,
                    shape = MbTheme.shapes.field,
                )
                .padding(horizontal = 14.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            if (leadingGlyph != null) {
                MbIcon(leadingGlyph, size = 16.dp, tint = MbTheme.colors.icon, strokeWidth = 1.9f)
            }
            Box(Modifier.weight(1f)) {
                if (value.isEmpty()) {
                    MbText(placeholder, MbTheme.type.bodySmall, MbTheme.colors.icon, maxLines = 1)
                }
                BasicTextField(
                    value = value,
                    onValueChange = onValueChange,
                    singleLine = singleLine,
                    readOnly = readOnly,
                    visualTransformation = visualTransformation,
                    textStyle = MbTheme.type.bodySmall.copy(
                        color = if (readOnly) MbTheme.colors.textSecondary else MbTheme.colors.ink
                    ),
                    cursorBrush = SolidColor(MbTheme.colors.accent),
                    keyboardOptions = KeyboardOptions(
                        keyboardType = keyboardType,
                        imeAction = imeAction,
                    ),
                    modifier = Modifier.fillMaxWidth(),
                )
            }
            trailing?.invoke()
        }
        if (error != null) {
            Spacer(Modifier.height(6.dp))
            MbText(error, MbTheme.type.caption, MbTheme.colors.danger)
        }
    }
}

/** The read-only search pill on the home screen; tapping opens the search page. */
@Composable
fun MbSearchPill(
    placeholder: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Row(
        modifier
            .fillMaxWidth()
            .height(MbTheme.dimens.searchHeight)
            .clip(MbTheme.shapes.field)
            .background(MbTheme.colors.canvas)
            .clickable(onClick = onClick)
            .padding(horizontal = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        MbIcon("search", size = 14.dp, tint = MbTheme.colors.icon, strokeWidth = 2f)
        MbText(placeholder, MbTheme.type.bodySmall, MbTheme.colors.icon, maxLines = 1)
    }
}

/** The live search field on screen 08. */
@Composable
fun MbSearchField(
    value: String,
    onValueChange: (String) -> Unit,
    onSubmit: () -> Unit,
    modifier: Modifier = Modifier,
    placeholder: String = stringResource(R.string.mahsulot_va_turkumlar_qidirish),
    autoFocus: Boolean = true,
) {
    val focus = remember { FocusRequester() }
    LaunchedEffect(autoFocus) { if (autoFocus) focus.requestFocus() }

    Row(
        modifier
            .fillMaxWidth()
            .height(MbTheme.dimens.searchHeight + 4.dp)
            .clip(MbTheme.shapes.field)
            .background(MbTheme.colors.fill)
            .padding(horizontal = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        MbIcon("search", size = 14.dp, tint = MbTheme.colors.icon, strokeWidth = 2f)
        Box(Modifier.weight(1f)) {
            if (value.isEmpty()) {
                MbText(placeholder, MbTheme.type.bodySmall, MbTheme.colors.icon, maxLines = 1)
            }
            BasicTextField(
                value = value,
                onValueChange = onValueChange,
                singleLine = true,
                textStyle = MbTheme.type.bodySmall.copy(color = MbTheme.colors.ink),
                cursorBrush = SolidColor(MbTheme.colors.accent),
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                keyboardActions = KeyboardActions(
                    onSearch = { onSubmit() },
                ),
                modifier = Modifier
                    .fillMaxWidth()
                    .focusRequester(focus),
            )
        }
        if (value.isNotEmpty()) {
            Box(
                Modifier
                    .size(18.dp)
                    .clip(CircleShape)
                    .background(MbTheme.colors.hairlineStrong)
                    .clickable { onValueChange("") },
                contentAlignment = Alignment.Center,
            ) {
                MbText("×", MbTheme.type.micro, Color.White)
            }
        }
    }
}

/**
 * Boxed code entry for the SMS screen and the PIN screens. Renders [length]
 * boxes over a single hidden field so the platform keyboard and autofill both
 * behave normally.
 */
@Composable
fun MbCodeField(
    value: String,
    onValueChange: (String) -> Unit,
    modifier: Modifier = Modifier,
    length: Int = 4,
    masked: Boolean = false,
    isError: Boolean = false,
) {
    val focus = remember { FocusRequester() }
    LaunchedEffect(Unit) { focus.requestFocus() }

    // The boxes share the row rather than taking a fixed width: six of them at
    // 54 dp overflowed a 411 dp screen once the page padding was taken off.
    Box(modifier.fillMaxWidth()) {
        BasicTextField(
            value = value,
            onValueChange = { if (it.length <= length && it.all(Char::isDigit)) onValueChange(it) },
            keyboardOptions = KeyboardOptions(
                keyboardType = KeyboardType.NumberPassword,
                imeAction = ImeAction.Done,
            ),
            visualTransformation = VisualTransformation.None,
            textStyle = MbTheme.type.body.copy(color = Color.Transparent),
            cursorBrush = SolidColor(Color.Transparent),
            modifier = Modifier
                .matchParentSize()
                .focusRequester(focus),
        )
        Row(
            Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(if (length > 4) 8.dp else 12.dp),
        ) {
            repeat(length) { index ->
                val char = value.getOrNull(index)
                val filled = char != null
                Box(
                    Modifier
                        .weight(1f)
                        .height(if (length > 4) 62.dp else 66.dp)
                        .clip(MbTheme.shapes.field)
                        .background(if (filled) MbTheme.colors.surface else MbTheme.colors.fill)
                        .border(
                            width = if (filled || isError) 1.6.dp else 0.dp,
                            color = when {
                                isError -> MbTheme.colors.danger
                                filled -> MbTheme.colors.ink
                                else -> Color.Transparent
                            },
                            shape = MbTheme.shapes.field,
                        ),
                    contentAlignment = Alignment.Center,
                ) {
                    if (char != null) {
                        if (masked) {
                            Box(
                                Modifier
                                    .size(12.dp)
                                    .clip(CircleShape)
                                    .background(MbTheme.colors.ink)
                            )
                        } else {
                            MbText(char.toString(), MbTheme.type.title1)
                        }
                    }
                }
            }
        }
    }
}

/**
 * −/+ stepper used in the cart, on the product page and in the picker sheet.
 *
 * [size] is the tap target for each end: the cart rows want the compact 34dp,
 * while a stepper standing next to a button wants that button's height so the
 * two read as one bar.
 */
@Composable
fun MbQuantityStepper(
    quantity: Int,
    onChange: (Int) -> Unit,
    modifier: Modifier = Modifier,
    min: Int = 1,
    max: Int = 99,
    size: Dp = 34.dp,
) {
    Row(
        modifier
            .clip(MbTheme.shapes.field)
            .background(MbTheme.colors.fill),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        StepperButton("−", enabled = quantity > min, size = size) { onChange(quantity - 1) }
        Box(Modifier.width(size), contentAlignment = Alignment.Center) {
            MbText(
                quantity.toString(),
                if (size >= 44.dp) MbTheme.type.title3 else MbTheme.type.label,
            )
        }
        StepperButton("+", enabled = quantity < max, size = size) { onChange(quantity + 1) }
    }
}

@Composable
private fun StepperButton(
    symbol: String,
    enabled: Boolean,
    size: Dp,
    onClick: () -> Unit,
) {
    Box(
        Modifier
            .size(size)
            // Round, like the button it sits in: a bare clickable washed a
            // square across the stepper's rounded corner.
            .clip(CircleShape)
            .clickable(enabled = enabled, onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        MbText(
            symbol,
            if (size >= 44.dp) MbTheme.type.title2 else MbTheme.type.title3,
            if (enabled) MbTheme.colors.ink else MbTheme.colors.disabled,
        )
    }
}
