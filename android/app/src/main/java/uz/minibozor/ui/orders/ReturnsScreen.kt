package uz.minibozor.ui.orders

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import uz.minibozor.R
import uz.minibozor.core.design.MbText
import uz.minibozor.core.design.MbTheme
import uz.minibozor.core.design.component.MbCard
import uz.minibozor.core.design.component.MbEmptyState
import uz.minibozor.core.design.component.MbLoading
import uz.minibozor.core.design.component.MbScreen
import uz.minibozor.core.design.component.MbStatusPill
import uz.minibozor.core.design.component.MbTopBar
import uz.minibozor.core.util.toLocalDateTimeOrNull
import uz.minibozor.core.util.uzDateTime

/**
 * Every return the customer has asked for, newest first.
 *
 * The profile's "Qaytarish" tile used to open the orders list, which is where
 * "Buyurtmalar" directly above it already went — two tiles, one screen, and no
 * way to see whether a request that had been sent was ever answered. The
 * request itself is made from an order; this is the other half of it, which is
 * what happened next.
 */
@Composable
fun ReturnsScreen(
    onBack: () -> Unit,
    viewModel: ReturnsViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()

    MbScreen(topBar = { MbTopBar(stringResource(R.string.qaytarishlarim), onBack = onBack) }) { padding ->
        when {
            state.loading && state.items.isEmpty() -> MbLoading(Modifier.padding(padding))

            state.items.isEmpty() -> MbEmptyState(
                glyph = "ret",
                title = stringResource(R.string.hali_qaytarish_arizasi_yubormagansiz),
                message = stringResource(
                    R.string.yetkazilgan_buyurtmani_14_kun_ichida_qaytarish_mumkin
                ),
                modifier = Modifier.padding(padding),
            )

            else -> LazyColumn(
                Modifier
                    .fillMaxSize()
                    .padding(padding),
                contentPadding = PaddingValues(12.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                items(state.items, key = { it.id }) { request ->
                    MbCard {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            MbText(
                                request.orderCode,
                                MbTheme.type.body.copy(fontWeight = FontWeight.Bold),
                                modifier = Modifier.weight(1f),
                            )
                            MbStatusPill(
                                stringResource(returnStatusLabel(request.status)),
                                returnStatusBackground(request.status),
                                returnStatusColor(request.status),
                            )
                        }
                        Spacer(Modifier.height(8.dp))
                        MbText(request.reason, MbTheme.type.bodySmall, MbTheme.colors.inkSoft)
                        if (request.comment.isNotBlank()) {
                            Spacer(Modifier.height(4.dp))
                            MbText(
                                request.comment,
                                MbTheme.type.caption,
                                MbTheme.colors.textSecondary,
                            )
                        }
                        Spacer(Modifier.height(8.dp))
                        MbText(
                            request.createdAt.toLocalDateTimeOrNull()?.uzDateTime().orEmpty(),
                            MbTheme.type.caption,
                            MbTheme.colors.textQuaternary,
                        )
                    }
                }
            }
        }
    }
}

private fun returnStatusLabel(status: String) = when (status) {
    "approved" -> R.string.return_approved
    "rejected" -> R.string.return_rejected
    "refunded" -> R.string.return_refunded
    else -> R.string.return_submitted
}

@Composable
private fun returnStatusBackground(status: String) = when (status) {
    "approved", "refunded" -> MbTheme.colors.successBg
    "rejected" -> MbTheme.colors.dangerBg
    else -> MbTheme.colors.warningBg
}

@Composable
private fun returnStatusColor(status: String) = when (status) {
    "approved", "refunded" -> MbTheme.colors.success
    "rejected" -> MbTheme.colors.danger
    else -> MbTheme.colors.warning
}
