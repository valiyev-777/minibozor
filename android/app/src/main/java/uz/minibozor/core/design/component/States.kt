package uz.minibozor.core.design.component

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.runtime.Composable
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import uz.minibozor.R
import uz.minibozor.core.design.MbText
import uz.minibozor.core.design.MbTheme
import uz.minibozor.core.design.icon.MbIcon

@Composable
fun MbLoading(modifier: Modifier = Modifier) {
    Box(modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        CircularProgressIndicator(color = MbTheme.colors.accent, strokeWidth = 2.5.dp)
    }
}

/**
 * Empty and error states share one layout — a soft circle with a glyph, a title,
 * a line of explanation and an optional action. The empty cart (screen 18) is
 * the canonical example.
 */
@Composable
fun MbEmptyState(
    glyph: String,
    title: String,
    message: String,
    modifier: Modifier = Modifier,
    actionLabel: String? = null,
    onAction: (() -> Unit)? = null,
) {
    Column(
        modifier
            .fillMaxWidth()
            .padding(horizontal = 40.dp, vertical = 48.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Box(
            Modifier
                .size(120.dp)
                .clip(CircleShape)
                .background(MbTheme.colors.onboardRing),
            contentAlignment = Alignment.Center,
        ) {
            MbIcon(glyph, size = 44.dp, tint = MbTheme.colors.hairlineStrong, strokeWidth = 1.4f)
        }
        Spacer(Modifier.height(22.dp))
        MbText(title, MbTheme.type.title2, textAlign = TextAlign.Center)
        Spacer(Modifier.height(8.dp))
        MbText(
            message,
            MbTheme.type.bodySmall,
            MbTheme.colors.textTertiary,
            textAlign = TextAlign.Center,
        )
        if (actionLabel != null && onAction != null) {
            Spacer(Modifier.height(24.dp))
            MbPrimaryButton(actionLabel, onAction)
        }
    }
}

@Composable
fun MbErrorState(
    message: String,
    onRetry: () -> Unit,
    modifier: Modifier = Modifier,
) = MbEmptyState(
    glyph = "ret",
    title = stringResource(R.string.nimadir_notogri_ketdi),
    message = message,
    modifier = modifier,
    actionLabel = stringResource(R.string.qayta_urinish),
    onAction = onRetry,
)

/** Grey block used while a list is loading. */
@Composable
fun MbSkeleton(
    modifier: Modifier = Modifier,
    height: androidx.compose.ui.unit.Dp = 16.dp,
) {
    Box(
        modifier
            .height(height)
            .clip(MbTheme.shapes.badge)
            .background(MbTheme.colors.fill)
    )
}
