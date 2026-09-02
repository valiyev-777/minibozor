package uz.minibozor.ui.profile

import androidx.compose.ui.res.pluralStringResource
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import uz.minibozor.R
import uz.minibozor.core.design.MbText
import uz.minibozor.core.design.MbTheme
import uz.minibozor.core.design.component.MbTabHeader
import uz.minibozor.core.design.component.MbCard
import uz.minibozor.core.design.component.MbDivider
import uz.minibozor.core.design.component.MbListRow
import uz.minibozor.core.design.component.MbScreen
import uz.minibozor.core.design.component.MbTabBarSpacer
import uz.minibozor.core.design.icon.MbIcon
import uz.minibozor.core.util.formatPhone

private data class QuickAction(val glyph: String, val label: String, val route: String)

/** Screen 30 — Profil. */
@Composable
fun ProfileScreen(
    onNavigate: (String) -> Unit,
    onSignedOut: () -> Unit,
    viewModel: ProfileViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val overview = state.overview
    var confirmSignOut by remember { mutableStateOf(false) }

    LaunchedEffect(state.signedOut) { if (state.signedOut) onSignedOut() }

    val quickActions = listOf(
        QuickAction("box", stringResource(R.string.buyurtmalar), "orders"),
        QuickAction("heart", stringResource(R.string.sevimlilar), "favorites"),
        QuickAction("star", stringResource(R.string.sharhlarim), "my_reviews"),
        QuickAction("ret", stringResource(R.string.qaytarish), "returns"),
    )

    MbScreen { padding ->
      Column(Modifier.fillMaxSize().padding(padding)) {
        // In the content, not the scaffold's top bar: that slot is laid out
        // above the window insets, so the name ended up under the clock.
        MbTabHeader(stringResource(R.string.tab_profile))
        LazyColumn(
            Modifier.fillMaxSize(),
            contentPadding = PaddingValues(12.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item {
                MbCard {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Box(
                            Modifier
                                .size(58.dp)
                                .clip(CircleShape)
                                .background(MbTheme.colors.fill),
                            contentAlignment = Alignment.Center,
                        ) {
                            MbIcon("user", size = 26.dp, tint = MbTheme.colors.icon)
                        }
                        Spacer(Modifier.size(14.dp))
                        Column(Modifier.weight(1f)) {
                            MbText(
                                overview?.user?.fullName?.ifBlank { stringResource(R.string.ismingizni_kiriting) }
                                    ?: "…",
                                MbTheme.type.title3,
                            )
                            MbText(
                                overview?.user?.phone?.formatPhone().orEmpty(),
                                MbTheme.type.bodySmall,
                                MbTheme.colors.textTertiary,
                            )
                        }
                        MbText(
                            stringResource(R.string.tahrirlash),
                            MbTheme.type.label,
                            MbTheme.colors.accent,
                            modifier = Modifier.clickable { onNavigate("personal") },
                        )
                    }
                }
            }

            item {
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    quickActions.forEach { action ->
                        Column(
                            Modifier
                                .weight(1f)
                                .clip(MbTheme.shapes.card)
                                .background(MbTheme.colors.surface)
                                .clickable { onNavigate(action.route) }
                                .padding(vertical = 16.dp),
                            horizontalAlignment = Alignment.CenterHorizontally,
                            verticalArrangement = Arrangement.spacedBy(8.dp),
                        ) {
                            MbIcon(action.glyph, size = 22.dp)
                            MbText(
                                action.label,
                                MbTheme.type.micro,
                                MbTheme.colors.textSecondary,
                                maxLines = 1,
                            )
                        }
                    }
                }
            }

            item {
                MbCard(padding = 6.dp) {
                    val rows = listOf(
                        Triple("card", stringResource(R.string.tolov_kartalari), pluralStringResource(
            R.plurals.n_items,
            overview?.cardsCount ?: 0,
            overview?.cardsCount ?: 0,
        )) to "cards",
                        Triple("pin", stringResource(R.string.manzillarim), pluralStringResource(
            R.plurals.n_items,
            overview?.addressesCount ?: 0,
            overview?.addressesCount ?: 0,
        )) to "addresses",
                        Triple("star", stringResource(R.string.sharhlarim), pluralStringResource(
            R.plurals.n_items,
            overview?.reviewsCount ?: 0,
            overview?.reviewsCount ?: 0,
        )) to "my_reviews",
                        Triple(
                            "bell",
                            stringResource(R.string.bildirishnomalar),
                            (overview?.unreadNotifications ?: 0).let {
                                if (it > 0) stringResource(R.string.n_yangi, it) else ""
                            },
                        ) to "notifications",
                        Triple("gear", stringResource(R.string.sozlamalar), "") to "settings",
                    )
                    rows.forEachIndexed { index, (row, route) ->
                        MbListRow(
                            label = row.second,
                            glyph = row.first,
                            meta = row.third.ifBlank { null },
                            onClick = { onNavigate(route) },
                            contentPadding = 10.dp,
                        )
                        if (index != rows.lastIndex) MbDivider(inset = 60.dp)
                    }
                }
            }

            item {
                MbCard(padding = 6.dp) {
                    MbListRow(
                        label = stringResource(R.string.hisobdan_chiqish),
                        glyph = "ret",
                        tint = MbTheme.colors.danger,
                        showChevron = false,
                        onClick = { confirmSignOut = true },
                        contentPadding = 10.dp,
                    )
                }
            }

            item { MbTabBarSpacer() }
        }
      }
    }

    if (confirmSignOut) {
        SignOutDialog(
            onDismiss = { confirmSignOut = false },
            onConfirm = {
                confirmSignOut = false
                viewModel.signOut()
            },
        )
    }
}
