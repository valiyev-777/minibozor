package uz.minibozor.ui.checkout

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
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import uz.minibozor.core.design.MbText
import uz.minibozor.core.design.MbTheme
import uz.minibozor.core.design.component.MbBottomBar
import uz.minibozor.core.design.component.MbCard
import uz.minibozor.core.design.component.MbKeyValueRow
import uz.minibozor.core.design.component.MbPrimaryButton
import uz.minibozor.core.design.component.MbScreen
import uz.minibozor.core.design.component.MbSecondaryButton
import uz.minibozor.core.design.icon.MbIcon
import uz.minibozor.core.util.sum
import uz.minibozor.core.util.toLocalDateTimeOrNull
import uz.minibozor.core.util.uzDateTime
import uz.minibozor.ui.orders.OrderDetailViewModel

/** Screen 24 — Buyurtma qabul qilindi. */
@Composable
fun OrderPlacedScreen(
    orderId: Int,
    onTrack: (Int) -> Unit,
    onGoHome: () -> Unit,
    viewModel: OrderDetailViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    LaunchedEffect(orderId) { viewModel.load(orderId) }
    val order = state.order

    MbScreen(
        background = MbTheme.colors.surface,
        bottomBar = {
            MbBottomBar {
                MbPrimaryButton("Buyurtmani kuzatish", { onTrack(orderId) }, leadingGlyph = "box")
                Spacer(Modifier.height(10.dp))
                MbSecondaryButton("Bosh sahifaga", onGoHome)
            }
        },
    ) { padding ->
        Column(
            Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Spacer(Modifier.height(40.dp))
            Box(
                Modifier
                    .size(96.dp)
                    .clip(CircleShape)
                    .background(MbTheme.colors.successBg),
                contentAlignment = Alignment.Center,
            ) {
                MbIcon("box", size = 40.dp, tint = MbTheme.colors.success, strokeWidth = 1.6f)
            }
            Spacer(Modifier.height(22.dp))
            MbText("Buyurtma qabul qilindi", MbTheme.type.title1, textAlign = TextAlign.Center)
            Spacer(Modifier.height(8.dp))
            MbText(
                order?.code?.let { "$it raqami bilan qabul qildik" }
                    ?: "Tez orada yig'ishni boshlaymiz",
                MbTheme.type.bodySmall,
                MbTheme.colors.textTertiary,
                textAlign = TextAlign.Center,
            )

            if (order != null) {
                Spacer(Modifier.height(26.dp))
                MbCard(background = MbTheme.colors.canvas) {
                    MbKeyValueRow("Buyurtma", order.code)
                    MbKeyValueRow(
                        "Sana",
                        order.createdAt.toLocalDateTimeOrNull()?.uzDateTime().orEmpty(),
                    )
                    MbKeyValueRow("Yetkazish", order.etaLabel)
                    MbKeyValueRow("To'lov", order.paymentLabel)
                    MbKeyValueRow("Jami", order.total.sum())
                }
            }
        }
    }
}
