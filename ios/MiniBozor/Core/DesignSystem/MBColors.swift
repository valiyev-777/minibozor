import SwiftUI

/// Palette from `design/tokens.json`.
///
/// The design ships a single light appearance, so these are plain constants
/// rather than a dynamic colour set — screens read them through `MB.color`.
struct MBColors {
    let accent = Color(hex: 0x0E7BF5)
    let accentTint = Color(hex: 0xEDEBFA)

    let ink = Color(hex: 0x0E0F12)
    let inkSoft = Color(hex: 0x3A4050)
    let inkMuted = Color(hex: 0x4A5060)
    let textSecondary = Color(hex: 0x6B7280)
    let textTertiary = Color(hex: 0x7C828E)
    let textQuaternary = Color(hex: 0x8A8F98)
    let icon = Color(hex: 0x9096A1)
    let placeholder = Color(hex: 0xAEB2BA)
    let disabled = Color(hex: 0xB7BCC5)

    let hairlineStrong = Color(hex: 0xCBCFD6)
    let hairline = Color(hex: 0xD7D9E0)
    let divider = Color(hex: 0xDDDFE5)
    let border = Color(hex: 0xEAEBEF)

    let surface = Color.white
    let surfaceAlt = Color(hex: 0xFCFCFD)
    let canvas = Color(hex: 0xF5F5F7)
    let fill = Color(hex: 0xF3F3F5)
    let fillCool = Color(hex: 0xF1F2F5)
    let photoWarm = Color(hex: 0xF4F3F1)
    let photoWarmAlt = Color(hex: 0xF2F1EE)
    let onboardRing = Color(hex: 0xEEF1F6)

    let danger = Color(hex: 0xE23A6A)
    let dangerBg = Color(hex: 0xFDF0F3)
    let dangerBorder = Color(hex: 0xF3D4DC)
    let success = Color(hex: 0x2F9E5E)
    let successBg = Color(hex: 0xEAF4EC)
    let warning = Color(hex: 0x8B6A16)
    let warningBg = Color(hex: 0xFCF3E3)
    let star = Color(hex: 0xE9A226)

    let heroFrom = Color(hex: 0x14162A)
    let cardFrom = Color(hex: 0x1F2444)
}

extension Color {
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
