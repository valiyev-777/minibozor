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

    /** Translucent slab behind the floating tab bar. */
    /**
     * A surface that is always the opposite of [canvas], with [onInverse] for
     * anything drawn on it — selected chips, the toast pill, the onboarding
     * button. The design draws these with `ink` on white, but `ink` inverts
     * with the theme, so pairing it with a fixed white leaves white on white
     * once the palette flips.
     */
    val inverse: Color = Color(0xFF0E0F12),
    val onInverse: Color = Color(0xFFFFFFFF),

    /**
     * The ground a product photograph sits on. Catalogue shots come on a light
     * studio backdrop, so this stays light in both themes — a dark one would
     * put a hard seam where a letterboxed photo ends and the frame begins.
     */
    val photoStudio: Color = Color(0xFFFFFFFF),

    /**
     * For labels sitting on a photo. Product shots are light whatever the
     * theme, so this pair stays dark-on-light in both.
     */
    val scrim: Color = Color(0xCC0E0F12),
    val onScrim: Color = Color(0xFFFFFFFF),

    val glass: Color = Color(0xF0FFFFFF),
    val isDark: Boolean = false,
) {
    companion object {
        /**
         * The design ships a single light appearance, so the dark palette is
         * derived from it: the neutral ramp is inverted, the accent is lifted a
         * little to keep contrast on dark ground, and the semantic colours keep
         * their hue with darker tinted backgrounds.
         */
        fun dark() = MbColors(
            accent = Color(0xFF3E97FF),
            accentTint = Color(0xFF20243A),

            ink = Color(0xFFF3F5F8),
            inkSoft = Color(0xFFC9CEDA),
            inkMuted = Color(0xFFB2B8C6),
            textSecondary = Color(0xFF9AA1B0),
            textTertiary = Color(0xFF8A90A0),
            textQuaternary = Color(0xFF7A8090),
            icon = Color(0xFF868D9C),
            placeholder = Color(0xFF6E7481),
            disabled = Color(0xFF3A3F4A),

            hairlineStrong = Color(0xFF454B57),
            hairline = Color(0xFF343A45),
            divider = Color(0xFF2C313B),
            border = Color(0xFF262B34),

            surface = Color(0xFF171A20),
            surfaceAlt = Color(0xFF1B1F26),
            canvas = Color(0xFF0F1116),
            fill = Color(0xFF20242C),
            fillCool = Color(0xFF1E222A),
            photoWarm = Color(0xFF23262C),
            photoWarmAlt = Color(0xFF212429),
            onboardRing = Color(0xFF1E222A),

            danger = Color(0xFFFF5C86),
            dangerBg = Color(0xFF33202A),
            dangerBorder = Color(0xFF4A2B37),
            success = Color(0xFF49BE7C),
            successBg = Color(0xFF1B2C24),
            warning = Color(0xFFD8A93F),
            warningBg = Color(0xFF2E2718),
            star = Color(0xFFF0B44A),

            heroFrom = Color(0xFF10121C),
            cardFrom = Color(0xFF1A1E33),

            inverse = Color(0xFFF3F5F8),
            onInverse = Color(0xFF0E0F12),
            // scrim and onScrim keep their defaults: a photo is light in
            // either theme, so the label on top of it does not flip.

            glass = Color(0xF01B1F26),
            isDark = true,
        )
    }
}
