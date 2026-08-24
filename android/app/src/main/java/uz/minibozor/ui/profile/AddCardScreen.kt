package uz.minibozor.ui.profile

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import uz.minibozor.core.design.MbText
import uz.minibozor.core.design.MbTheme
import uz.minibozor.core.design.component.MbBottomBar
import uz.minibozor.core.design.component.MbCard
import uz.minibozor.core.design.component.MbListRow
import uz.minibozor.core.design.component.MbPrimaryButton
import uz.minibozor.core.design.component.MbScreen
import uz.minibozor.core.design.component.MbTopBar
import uz.minibozor.core.design.icon.MbIcon

/**
 * Adding a card.
 *
 * The card number is deliberately **not** collected here. The processor's own
 * SDK or 3-D Secure webview takes the PAN and returns a token, which is the only
 * thing `POST /payment-cards` accepts. Wire [onLaunchProvider] to that SDK; the
 * rest of the app never sees a card number, so the app stays out of PCI scope.
 */
@Composable
fun AddCardScreen(
    onBack: () -> Unit,
    onLaunchProvider: () -> Unit,
) {
    MbScreen(
        topBar = { MbTopBar("Karta qo'shish", onBack = onBack) },
        bottomBar = {
            MbBottomBar {
                MbPrimaryButton("Xavfsiz oynani ochish", onLaunchProvider, leadingGlyph = "card")
            }
        },
    ) { padding ->
        Column(
            Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(12.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Spacer(Modifier.height(24.dp))
            Box(
                Modifier
                    .size(88.dp)
                    .clip(CircleShape)
                    .background(MbTheme.colors.accentTint),
                contentAlignment = Alignment.Center,
            ) {
                MbIcon("card", size = 36.dp, tint = MbTheme.colors.accent, strokeWidth = 1.6f)
            }
            Spacer(Modifier.height(20.dp))
            MbText("Karta ma'lumotlari himoyalangan", MbTheme.type.title3, textAlign = TextAlign.Center)
            Spacer(Modifier.height(8.dp))
            MbText(
                "Karta raqamini to'lov tizimining xavfsiz oynasida kiritasiz. " +
                    "Mini Bozor faqat kartaning oxirgi 4 raqamini saqlaydi.",
                MbTheme.type.bodySmall,
                MbTheme.colors.textTertiary,
                textAlign = TextAlign.Center,
            )
            Spacer(Modifier.height(24.dp))
            MbCard(padding = 6.dp) {
                MbListRow(
                    label = "Humo va UzCard",
                    subtitle = "Milliy to'lov tizimlari",
                    glyph = "card",
                    showChevron = false,
                    modifier = Modifier.padding(horizontal = 10.dp),
                )
                MbListRow(
                    label = "Visa va Mastercard",
                    subtitle = "Xalqaro kartalar",
                    glyph = "globe",
                    showChevron = false,
                    modifier = Modifier.padding(horizontal = 10.dp),
                )
            }
        }
    }
}
