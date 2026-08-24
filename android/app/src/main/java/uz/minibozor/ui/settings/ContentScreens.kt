package uz.minibozor.ui.settings

import androidx.compose.animation.AnimatedVisibility
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
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import uz.minibozor.core.design.MbText
import uz.minibozor.core.design.MbTheme
import uz.minibozor.core.design.component.MbCard
import uz.minibozor.core.design.component.MbDivider
import uz.minibozor.core.design.component.MbListRow
import uz.minibozor.core.design.component.MbScreen
import uz.minibozor.core.design.component.MbTopBar
import uz.minibozor.core.design.component.SectionHeader
import uz.minibozor.core.design.icon.MbIcon

/** Screen 45 — Yordam markazi. */
@Composable
fun HelpScreen(
    onBack: () -> Unit,
    viewModel: ContentViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    var expanded by remember { mutableStateOf<Int?>(null) }

    MbScreen(topBar = { MbTopBar("Yordam markazi", onBack = onBack) }) { padding ->
        LazyColumn(
            Modifier
                .fillMaxSize()
                .padding(padding),
            contentPadding = PaddingValues(12.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item {
                MbCard(padding = 6.dp) {
                    MbListRow(
                        label = "Qo'ng'iroq qilish",
                        subtitle = state.support["hours"],
                        glyph = "headset",
                        meta = state.support["phone"],
                        modifier = Modifier.padding(horizontal = 10.dp),
                    )
                    MbDivider(inset = 60.dp)
                    MbListRow(
                        label = "Telegram orqali yozish",
                        subtitle = "Odatda 5 daqiqada javob beramiz",
                        glyph = "phone",
                        modifier = Modifier.padding(horizontal = 10.dp),
                    )
                }
            }

            item {
                MbText(
                    "Ko'p so'raladigan savollar",
                    MbTheme.type.captionBold,
                    MbTheme.colors.textSecondary,
                    modifier = Modifier.padding(start = 6.dp),
                )
            }

            item {
                MbCard(padding = 6.dp) {
                    state.faq.forEachIndexed { index, item ->
                        Column(
                            Modifier
                                .fillMaxWidth()
                                .clickable {
                                    expanded = if (expanded == item.id) null else item.id
                                }
                                .padding(horizontal = 10.dp, vertical = 14.dp)
                        ) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                MbText(
                                    item.question,
                                    MbTheme.type.body.copy(
                                        fontWeight =
                                        androidx.compose.ui.text.font.FontWeight.Bold),
                                    modifier = Modifier.weight(1f),
                                )
                                MbText(
                                    if (expanded == item.id) "−" else "+",
                                    MbTheme.type.title3,
                                    MbTheme.colors.hairlineStrong,
                                )
                            }
                            AnimatedVisibility(expanded == item.id) {
                                Column {
                                    Spacer(Modifier.height(8.dp))
                                    MbText(
                                        item.answer,
                                        MbTheme.type.bodySmall,
                                        MbTheme.colors.textSecondary,
                                    )
                                }
                            }
                        }
                        if (index != state.faq.lastIndex) MbDivider()
                    }
                }
            }
        }
    }
}

/** Screen 46 — Shartlar va maxfiylik. */
@Composable
fun LegalScreen(
    onBack: () -> Unit,
    onOpenDoc: (String) -> Unit,
    viewModel: ContentViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()

    MbScreen(topBar = { MbTopBar("Shartlar va maxfiylik", onBack = onBack) }) { padding ->
        Column(
            Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(12.dp)
        ) {
            MbCard(padding = 6.dp) {
                state.docs.forEachIndexed { index, doc ->
                    MbListRow(
                        label = doc.title,
                        subtitle = doc.meta.ifBlank { null },
                        glyph = doc.icon,
                        onClick = { onOpenDoc(doc.slug) },
                        modifier = Modifier.padding(horizontal = 10.dp),
                    )
                    if (index != state.docs.lastIndex) MbDivider(inset = 60.dp)
                }
            }
        }
    }
}

/** One legal document. */
@Composable
fun LegalDocScreen(
    slug: String,
    onBack: () -> Unit,
    viewModel: ContentViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    LaunchedEffect(slug) { viewModel.loadDoc(slug) }

    MbScreen(topBar = { MbTopBar(state.doc?.title ?: "Hujjat", onBack = onBack) }) { padding ->
        Column(
            Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState())
                .padding(12.dp)
        ) {
            MbCard {
                MbText(state.doc?.meta.orEmpty(), MbTheme.type.caption, MbTheme.colors.icon)
                Spacer(Modifier.height(12.dp))
                MbText(
                    state.doc?.body.orEmpty(),
                    MbTheme.type.bodySmall,
                    MbTheme.colors.inkSoft,
                )
            }
        }
    }
}
