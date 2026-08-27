package uz.minibozor.ui.settings

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
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.runtime.Composable
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
import uz.minibozor.core.design.component.MbCard
import uz.minibozor.core.design.component.MbDivider
import uz.minibozor.core.design.component.MbEmptyState
import uz.minibozor.core.design.component.MbListRow
import uz.minibozor.core.design.component.MbRadioRow
import uz.minibozor.core.design.component.MbScreen
import uz.minibozor.core.design.component.MbToggleRow
import uz.minibozor.core.design.component.MbTopBar
import uz.minibozor.core.design.component.SectionHeader
import uz.minibozor.core.design.icon.MbIcon
import uz.minibozor.core.util.toLocalDateTimeOrNull
import uz.minibozor.core.util.uzRelative
import uz.minibozor.data.remote.dto.NotificationPrefsRequest
import uz.minibozor.ui.profile.NotificationsViewModel

/** Screen 36 — Bildirishnomalar. */
@Composable
fun NotificationsScreen(
    onBack: () -> Unit,
    onOpenDeepLink: (String) -> Unit,
    viewModel: NotificationsViewModel = hiltViewModel(),
) {
    val groups by viewModel.groups.collectAsStateWithLifecycle()

    MbScreen(
        topBar = {
            MbTopBar(
                title = stringResource(R.string.bildirishnomalar),
                onBack = onBack,
                action = {
                    MbIcon(
                        "bell",
                        size = 20.dp,
                        tint = MbTheme.colors.accent,
                        modifier = Modifier.clickable { viewModel.markAllRead() },
                    )
                },
            )
        },
    ) { padding ->
        if (groups.isEmpty()) {
            MbEmptyState(
                glyph = "bell",
                title = stringResource(R.string.bildirishnoma_yoq),
                message = stringResource(R.string.buyurtma_holati_va_chegirmalar_haqida_shu),
                modifier = Modifier.padding(padding),
            )
            return@MbScreen
        }

        LazyColumn(
            Modifier
                .fillMaxSize()
                .padding(padding),
            contentPadding = PaddingValues(12.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            groups.forEach { group ->
                item(key = group.label) {
                    MbText(
                        group.label,
                        MbTheme.type.captionBold,
                        MbTheme.colors.textSecondary,
                        modifier = Modifier.padding(start = 6.dp, top = 4.dp),
                    )
                }
                item(key = "${group.label}-items") {
                    MbCard(padding = 6.dp) {
                        group.items.forEachIndexed { index, item ->
                            Row(
                                Modifier
                                    .fillMaxWidth()
                                    .clickable {
                                        item.deepLink?.let(onOpenDeepLink)
                                    }
                                    .padding(horizontal = 10.dp, vertical = 12.dp),
                                horizontalArrangement = Arrangement.spacedBy(12.dp),
                            ) {
                                Box(
                                    Modifier
                                        .size(38.dp)
                                        .clip(MbTheme.shapes.field)
                                        .background(MbTheme.colors.fill),
                                    contentAlignment = Alignment.Center,
                                ) {
                                    MbIcon(item.icon, size = 18.dp)
                                }
                                Column(Modifier.weight(1f)) {
                                    Row(verticalAlignment = Alignment.CenterVertically) {
                                        MbText(
                                            item.title,
                                            MbTheme.type.body.copy(
                                                fontWeight =
                                                androidx.compose.ui.text.font.FontWeight.Bold),
                                            modifier = Modifier.weight(1f),
                                            maxLines = 1,
                                        )
                                        if (!item.read) {
                                            Box(
                                                Modifier
                                                    .size(7.dp)
                                                    .clip(CircleShape)
                                                    .background(MbTheme.colors.accent)
                                            )
                                        }
                                    }
                                    MbText(item.text, MbTheme.type.meta, MbTheme.colors.textSecondary)
                                    MbText(
                                        item.createdAt.toLocalDateTimeOrNull()?.uzRelative()
                                            .orEmpty(),
                                        MbTheme.type.micro,
                                        MbTheme.colors.disabled,
                                    )
                                }
                            }
                            if (index != group.items.lastIndex) MbDivider(inset = 60.dp)
                        }
                    }
                }
            }
        }
    }
}

/** Screen 37 — Sozlamalar. */
@Composable
fun SettingsScreen(
    onBack: () -> Unit,
    onNavigate: (String) -> Unit,
    viewModel: SettingsViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()

    MbScreen(topBar = { MbTopBar(stringResource(R.string.sozlamalar), onBack = onBack) }) { padding ->
        LazyColumn(
            Modifier
                .fillMaxSize()
                .padding(padding),
            contentPadding = PaddingValues(12.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item {
                MbCard(padding = 6.dp) {
                    val rows = listOf(
                        Triple("bell", stringResource(R.string.bildirishnoma_sozlamalari), stringResource(R.string.push_sms)) to
                            "notification_settings",
                        Triple(
                            "globe",
                            stringResource(R.string.ilova_tili),
                            languageLabel(state.language),
                        ) to "language",
                        Triple(
                            "gear",
                            stringResource(R.string.xavfsizlik),
                            if (state.hasPin) stringResource(R.string.pin_yoqilgan) else stringResource(R.string.pin_ornatilmagan),
                        ) to "security",
                        Triple("headset", stringResource(R.string.yordam_markazi), "1150") to "help",
                        Triple("ret", stringResource(R.string.shartlar_va_maxfiylik), "") to "legal",
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
                    MbToggleRow(
                        label = stringResource(R.string.joylashuv),
                        subtitle = stringResource(R.string.yaqin_punktlarni_korsatish),
                        glyph = "pin",
                        checked = state.settings?.locationEnabled ?: true,
                        onCheckedChange = viewModel::setLocation,
                        contentPadding = 10.dp,
                    )
                    MbDivider(inset = 60.dp)
                    MbToggleRow(
                        label = stringResource(R.string.tungi_rejim),
                        subtitle = stringResource(R.string.tizim_bilan_moslashadi),
                        glyph = "gear",
                        checked = state.settings?.nightMode ?: false,
                        onCheckedChange = viewModel::setNightMode,
                        contentPadding = 10.dp,
                    )
                }
            }

            item {
                MbText(
                    stringResource(R.string.mini_bozor_versiya_1_0),
                    MbTheme.type.caption,
                    MbTheme.colors.disabled,
                    modifier = Modifier.padding(horizontal = 6.dp),
                )
            }
        }
    }
}

/** Screen 38 — Bildirishnoma sozlamalari. */
@Composable
fun NotificationSettingsScreen(
    onBack: () -> Unit,
    viewModel: SettingsViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val prefs = state.prefs

    MbScreen(topBar = { MbTopBar(stringResource(R.string.bildirishnomalar), onBack = onBack) }) { padding ->
        Column(
            Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            MbCard(padding = 6.dp) {
                MbToggleRow(
                    label = stringResource(R.string.buyurtma_holati),
                    subtitle = stringResource(R.string.yigildi_yolda_yetkazildi),
                    glyph = "box",
                    checked = prefs?.orderStatus ?: true,
                    onCheckedChange = { viewModel.setPref(NotificationPrefsRequest(orderStatus = it)) },
                    contentPadding = 10.dp,
                )
                MbDivider(inset = 60.dp)
                MbToggleRow(
                    label = stringResource(R.string.chegirma_va_aksiyalar),
                    subtitle = stringResource(R.string.haftada_2_martadan_kop_emas),
                    glyph = "gift",
                    checked = prefs?.promotions ?: true,
                    onCheckedChange = { viewModel.setPref(NotificationPrefsRequest(promotions = it)) },
                    contentPadding = 10.dp,
                )
                MbDivider(inset = 60.dp)
                MbToggleRow(
                    label = stringResource(R.string.sevimlilar_narxi),
                    subtitle = stringResource(R.string.narx_tushganda_xabar),
                    glyph = "heart",
                    checked = prefs?.priceDrop ?: true,
                    onCheckedChange = { viewModel.setPref(NotificationPrefsRequest(priceDrop = it)) },
                    contentPadding = 10.dp,
                )
            }

            MbCard(padding = 6.dp) {
                SectionHeader(
                    stringResource(R.string.kanallar),
                    modifier = Modifier.padding(horizontal = 10.dp, vertical = 8.dp),
                )
                MbToggleRow(
                    label = stringResource(R.string.push_bildirishnoma),
                    glyph = "bell",
                    checked = prefs?.push ?: true,
                    onCheckedChange = { viewModel.setPref(NotificationPrefsRequest(push = it)) },
                    contentPadding = 10.dp,
                )
                MbDivider(inset = 60.dp)
                MbToggleRow(
                    label = stringResource(R.string.sms),
                    glyph = "phone",
                    checked = prefs?.sms ?: true,
                    onCheckedChange = { viewModel.setPref(NotificationPrefsRequest(sms = it)) },
                    contentPadding = 10.dp,
                )
            }
        }
    }
}

/** Screen 39 — Til. */
@Composable
fun LanguageScreen(
    onBack: () -> Unit,
    viewModel: SettingsViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()

    MbScreen(topBar = { MbTopBar(stringResource(R.string.ilova_tili), onBack = onBack) }) { padding ->
        Column(
            Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(12.dp)
        ) {
            MbCard(padding = 6.dp) {
                state.languages.forEachIndexed { index, language ->
                    val code = language["code"].orEmpty()
                    MbRadioRow(
                        label = language["label"].orEmpty(),
                        subtitle = language["native"],
                        selected = state.language == code,
                        onSelect = { viewModel.setLanguage(code) },
                        leading = {
                            Box(
                                Modifier
                                    .size(38.dp)
                                    .clip(MbTheme.shapes.field)
                                    .background(MbTheme.colors.fill),
                                contentAlignment = Alignment.Center,
                            ) {
                                MbText(
                                    code.uppercase(),
                                    MbTheme.type.micro,
                                    MbTheme.colors.textSecondary,
                                )
                            }
                        },
                        contentPadding = 10.dp,
                    )
                    if (index != state.languages.lastIndex) MbDivider(inset = 60.dp)
                }
            }
            Spacer(Modifier.height(12.dp))
            MbText(
                stringResource(R.string.tanlangan_til_darhol_qollanadi_turkum),
                MbTheme.type.caption,
                MbTheme.colors.textQuaternary,
                modifier = Modifier.padding(horizontal = 6.dp),
            )
        }
    }
}

/** Screen 40 — Xavfsizlik. */
@Composable
fun SecurityScreen(
    onBack: () -> Unit,
    onChangePin: () -> Unit,
    viewModel: SettingsViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()

    MbScreen(topBar = { MbTopBar(stringResource(R.string.xavfsizlik), onBack = onBack) }) { padding ->
        Column(
            Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            MbCard(padding = 6.dp) {
                MbListRow(
                    label = if (state.hasPin) stringResource(R.string.pin_kodni_ozgartirish) else stringResource(R.string.pin_kod_ornatish),
                    subtitle = stringResource(R.string.ilovaga_kirishda_soraladi),
                    glyph = "gear",
                    onClick = onChangePin,
                    contentPadding = 10.dp,
                )
                MbDivider(inset = 60.dp)
                MbToggleRow(
                    label = stringResource(R.string.face_id_barmoq_izi),
                    subtitle = stringResource(R.string.pin_orniga_biometrika),
                    glyph = "user",
                    checked = state.biometrics,
                    onCheckedChange = viewModel::setBiometrics,
                    contentPadding = 10.dp,
                )
            }

            MbText(
                stringResource(R.string.pin_kod_ilovani_ochishda_soraladi_unutib),
                MbTheme.type.caption,
                MbTheme.colors.textQuaternary,
                modifier = Modifier.padding(horizontal = 6.dp),
            )
        }
    }
}

private fun languageLabel(code: String?): String = when (code) {
    "ru" -> "Русский"
    "en" -> "English"
    else -> "O'zbekcha"
}
