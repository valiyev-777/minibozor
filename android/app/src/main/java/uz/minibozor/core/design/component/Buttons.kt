package uz.minibozor.core.design.component

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import uz.minibozor.core.design.MbText
import uz.minibozor.core.design.MbTheme
import uz.minibozor.core.design.icon.MbIcon

/** Filled accent button — the main call to action on almost every screen. */
@Composable
fun MbPrimaryButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    loading: Boolean = false,
    leadingGlyph: String? = null,
    container: Color = MbTheme.colors.accent,
    contentColor: Color = Color.White,
) {
    val interaction = remember { MutableInteractionSource() }
    val pressed by interaction.collectIsPressedAsState()
    val scale by animateFloatAsState(if (pressed) 0.98f else 1f, label = "press")

    Row(
        modifier
            .fillMaxWidth()
            .scale(scale)
            .height(MbTheme.dimens.buttonHeight)
            .clip(MbTheme.shapes.button)
            .background(if (enabled) container else MbTheme.colors.disabled)
            .clickable(
                enabled = enabled && !loading,
                interactionSource = interaction,
                indication = null,
                onClick = onClick,
            ),
        horizontalArrangement = Arrangement.Center,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (loading) {
            CircularProgressIndicator(
                color = contentColor,
                strokeWidth = 2.dp,
                modifier = Modifier.size(18.dp),
            )
        } else {
            if (leadingGlyph != null) {
                MbIcon(leadingGlyph, size = 18.dp, tint = contentColor, strokeWidth = 1.9f)
                Box(Modifier.size(8.dp))
            }
            MbText(text, MbTheme.type.label.copy(fontSize = MbTheme.type.body.fontSize), contentColor)
        }
    }
}

/** Outlined button — "Bekor qilish", secondary paths. */
@Composable
fun MbSecondaryButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    contentColor: Color = MbTheme.colors.ink,
) {
    Row(
        modifier
            .fillMaxWidth()
            .height(MbTheme.dimens.buttonHeight)
            .clip(MbTheme.shapes.button)
            .background(MbTheme.colors.surface)
            .border(1.dp, MbTheme.colors.border, MbTheme.shapes.button)
            .clickable(enabled = enabled, onClick = onClick)
            .alpha(if (enabled) 1f else 0.5f),
        horizontalArrangement = Arrangement.Center,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        MbText(text, MbTheme.type.label.copy(fontSize = MbTheme.type.body.fontSize), contentColor)
    }
}

/** Destructive action — "Buyurtmani bekor qilish", "Hisobdan chiqish". */
@Composable
fun MbDangerButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    loading: Boolean = false,
) = MbPrimaryButton(
    text = text,
    onClick = onClick,
    modifier = modifier,
    loading = loading,
    container = MbTheme.colors.danger,
)

/** A pinned footer: white, hairline on top, safe-area aware. */
@Composable
fun MbBottomBar(
    modifier: Modifier = Modifier,
    content: @Composable () -> Unit,
) {
    Column(
        modifier
            .fillMaxWidth()
            .background(MbTheme.colors.surface)
            .windowInsetsPadding(WindowInsets.navigationBars)
            .padding(horizontal = 20.dp, vertical = 14.dp)
    ) {
        content()
    }
}
