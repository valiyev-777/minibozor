import SwiftUI

/// Palette from `design/tokens.json`.
///
/// Every colour resolves itself by the current appearance, so the palette stays
/// one set of constants and no screen has to know which one is in force. The
/// design ships a single light appearance; the dark ramp is inverted from it,
/// the accent lifted a little to hold contrast on dark ground, and the semantic
/// colours keep their hue over darker tinted backgrounds.
struct MBColors {
    let accent = Color.adaptive(light: 0x0E7BF5, dark: 0x3E97FF)
    let accentTint = Color.adaptive(light: 0xEDEBFA, dark: 0x20243A)

    let ink = Color.adaptive(light: 0x0E0F12, dark: 0xF3F5F8)
    let inkSoft = Color.adaptive(light: 0x3A4050, dark: 0xC9CEDA)
    let inkMuted = Color.adaptive(light: 0x4A5060, dark: 0xB2B8C6)
    let textSecondary = Color.adaptive(light: 0x6B7280, dark: 0x9AA1B0)
    let textTertiary = Color.adaptive(light: 0x7C828E, dark: 0x8A90A0)
    let textQuaternary = Color.adaptive(light: 0x8A8F98, dark: 0x7A8090)
    let icon = Color.adaptive(light: 0x9096A1, dark: 0x868D9C)
    let placeholder = Color.adaptive(light: 0xAEB2BA, dark: 0x6E7481)
    let disabled = Color.adaptive(light: 0xB7BCC5, dark: 0x3A3F4A)

    let hairlineStrong = Color.adaptive(light: 0xCBCFD6, dark: 0x454B57)
    let hairline = Color.adaptive(light: 0xD7D9E0, dark: 0x343A45)
    let divider = Color.adaptive(light: 0xDDDFE5, dark: 0x2C313B)
    let border = Color.adaptive(light: 0xEAEBEF, dark: 0x262B34)

    let surface = Color.adaptive(light: 0xFFFFFF, dark: 0x171A20)
    let surfaceAlt = Color.adaptive(light: 0xFCFCFD, dark: 0x1B1F26)
    let canvas = Color.adaptive(light: 0xF5F5F7, dark: 0x0F1116)
    let fill = Color.adaptive(light: 0xF3F3F5, dark: 0x20242C)
    let fillCool = Color.adaptive(light: 0xF1F2F5, dark: 0x1E222A)
    let photoWarm = Color.adaptive(light: 0xF4F3F1, dark: 0x23262C)
    let photoWarmAlt = Color.adaptive(light: 0xF2F1EE, dark: 0x212429)
    let onboardRing = Color.adaptive(light: 0xEEF1F6, dark: 0x1E222A)

    let danger = Color.adaptive(light: 0xE23A6A, dark: 0xFF5C86)
    let dangerBg = Color.adaptive(light: 0xFDF0F3, dark: 0x33202A)
    let dangerBorder = Color.adaptive(light: 0xF3D4DC, dark: 0x4A2B37)
    let success = Color.adaptive(light: 0x2F9E5E, dark: 0x49BE7C)
    let successBg = Color.adaptive(light: 0xEAF4EC, dark: 0x1B2C24)
    let warning = Color.adaptive(light: 0x8B6A16, dark: 0xD8A93F)
    let warningBg = Color.adaptive(light: 0xFCF3E3, dark: 0x2E2718)
    let star = Color.adaptive(light: 0xE9A226, dark: 0xF0B44A)

    let heroFrom = Color.adaptive(light: 0x14162A, dark: 0x10121C)
    let cardFrom = Color.adaptive(light: 0x1F2444, dark: 0x1A1E33)

    /// The translucent slab the tab bar sits on.
    let glass = Color.adaptive(light: 0xFFFFFF, dark: 0x1B1F26, opacity: 0.94)

    /// A surface that is always the opposite of `canvas`, with `onInverse` for
    /// anything drawn on it — selected chips, the toast pill. The design draws
    /// these with `ink` on white, but `ink` inverts with the appearance, so
    /// pairing it with a fixed white leaves white on white once it flips.
    let inverse = Color.adaptive(light: 0x0E0F12, dark: 0xF3F5F8)
    let onInverse = Color.adaptive(light: 0xFFFFFF, dark: 0x0E0F12)

    /// For labels on a photograph, and for the ground a photograph sits on.
    /// Product shots are light whatever the appearance, so these do not flip.
    let scrim = Color(hex: 0x0E0F12, alpha: 0.8)
    let onScrim = Color.white
    let photoStudio = Color.white
}

extension Color {
    /// One colour that resolves itself by the current appearance.
    ///
    /// A dynamic UIColor rather than an environment value, so the palette stays
    /// a plain set of constants and none of the screens have to be told which
    /// appearance is in force.
    static func adaptive(light: UInt32, dark: UInt32, opacity: Double = 1) -> Color {
        Color(UIColor { traits in
            let value = traits.userInterfaceStyle == .dark ? dark : light
            return UIColor(
                red: CGFloat((value >> 16) & 0xFF) / 255,
                green: CGFloat((value >> 8) & 0xFF) / 255,
                blue: CGFloat(value & 0xFF) / 255,
                alpha: opacity
            )
        })
    }

    init(hex: UInt32, alpha: Double = 1) {
        self.init(
            .sRGB,
            red: Double((hex >> 16) & 0xFF) / 255,
            green: Double((hex >> 8) & 0xFF) / 255,
            blue: Double(hex & 0xFF) / 255,
            opacity: alpha
        )
    }

    /// `#14162A` as sent by the API, with a safe fallback.
    init(hexString: String, fallback: Color = .black) {
        var text = hexString.trimmingCharacters(in: .whitespacesAndNewlines)
        if text.hasPrefix("#") { text.removeFirst() }
        guard text.count == 6, let value = UInt32(text, radix: 16) else {
            self = fallback
            return
        }
        self.init(hex: value)
    }
}
