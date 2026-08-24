package uz.minibozor.core.design

import androidx.compose.runtime.Immutable
import androidx.compose.ui.graphics.Color

/**
 * Palette lifted from `design/tokens.json`. The design is a single light theme,
 * so these are plain constants rather than a Material colour scheme — screens
 * reference them through [MbTheme.colors].
 */
@Immutable
data class MbColors(
    val accent: Color = Color(0xFF0E7BF5),
    val accentTint: Color = Color(0xFFEDEBFA),

    val ink: Color = Color(0xFF0E0F12),
    val inkSoft: Color = Color(0xFF3A4050),
    val inkMuted: Color = Color(0xFF4A5060),
    val textSecondary: Color = Color(0xFF6B7280),
    val textTertiary: Color = Color(0xFF7C828E),
    val textQuaternary: Color = Color(0xFF8A8F98),
    val icon: Color = Color(0xFF9096A1),
    val placeholder: Color = Color(0xFFAEB2BA),
    val disabled: Color = Color(0xFFB7BCC5),

    val hairlineStrong: Color = Color(0xFFCBCFD6),
    val hairline: Color = Color(0xFFD7D9E0),
    val divider: Color = Color(0xFFDDDFE5),
    val border: Color = Color(0xFFEAEBEF),

    val surface: Color = Color(0xFFFFFFFF),
    val surfaceAlt: Color = Color(0xFFFCFCFD),
    val canvas: Color = Color(0xFFF5F5F7),
    val fill: Color = Color(0xFFF3F3F5),
    val fillCool: Color = Color(0xFFF1F2F5),
    val photoWarm: Color = Color(0xFFF4F3F1),
    val photoWarmAlt: Color = Color(0xFFF2F1EE),
    val onboardRing: Color = Color(0xFFEEF1F6),

    val danger: Color = Color(0xFFE23A6A),
    val dangerBg: Color = Color(0xFFFDF0F3),
    val dangerBorder: Color = Color(0xFFF3D4DC),
    val success: Color = Color(0xFF2F9E5E),
    val successBg: Color = Color(0xFFEAF4EC),
    val warning: Color = Color(0xFF8B6A16),
    val warningBg: Color = Color(0xFFFCF3E3),
    val star: Color = Color(0xFFE9A226),

    val heroFrom: Color = Color(0xFF14162A),
    val cardFrom: Color = Color(0xFF1F2444),
)
