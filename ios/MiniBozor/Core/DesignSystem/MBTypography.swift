import SwiftUI

/// The design's type scale.
///
/// It is set in Plus Jakarta Sans. No font binaries are bundled: drop the TTFs
/// into the target, list them under `UIAppFonts` in Info.plist, and change
/// `familyName` below — every style already asks for the right weight and size.
struct MBTypography {
    /// Set to e.g. `"PlusJakartaSans"` once the font files are added.
    static let familyName: String? = nil

    struct Style {
        let size: CGFloat
        let weight: Font.Weight
        let tracking: CGFloat
        let lineSpacingRatio: CGFloat

        var font: Font {
            if let family = MBTypography.familyName {
                return .custom(family, size: size).weight(weight)
            }
            return .system(size: size, weight: weight, design: .default)
        }

        /// SwiftUI's `lineSpacing` is the gap *between* lines, not the box, so
        /// the design's multiplier has to be converted.
        var lineSpacing: CGFloat { max(0, size * (lineSpacingRatio - 1)) }
    }

    let display = Style(size: 27, weight: .heavy, tracking: -0.9, lineSpacingRatio: 1.16)
    let title1 = Style(size: 23, weight: .heavy, tracking: -0.6, lineSpacingRatio: 1.15)
    let title2 = Style(size: 20, weight: .heavy, tracking: -0.4, lineSpacingRatio: 1.2)
    let title3 = Style(size: 17, weight: .heavy, tracking: -0.3, lineSpacingRatio: 1.25)
    let sectionHead = Style(size: 15.5, weight: .heavy, tracking: -0.2, lineSpacingRatio: 1.25)
    let price = Style(size: 15.5, weight: .heavy, tracking: -0.3, lineSpacingRatio: 1.2)
    let priceSmall = Style(size: 14, weight: .heavy, tracking: -0.3, lineSpacingRatio: 1.2)
    let statusBar = Style(size: 14.5, weight: .bold, tracking: 0, lineSpacingRatio: 1.2)
    let body = Style(size: 13, weight: .medium, tracking: 0, lineSpacingRatio: 1.45)
    let bodyBold = Style(size: 13, weight: .bold, tracking: 0, lineSpacingRatio: 1.45)
    let bodySmall = Style(size: 12.5, weight: .medium, tracking: 0, lineSpacingRatio: 1.6)
    let label = Style(size: 11.5, weight: .bold, tracking: 0, lineSpacingRatio: 1.3)
    let caption = Style(size: 11, weight: .medium, tracking: 0, lineSpacingRatio: 1.35)
    let captionBold = Style(size: 11, weight: .bold, tracking: 1.4, lineSpacingRatio: 1.3)
    let meta = Style(size: 10.5, weight: .medium, tracking: 0, lineSpacingRatio: 1.35)
    let micro = Style(size: 9.5, weight: .bold, tracking: 0, lineSpacingRatio: 1.2)
    let badge = Style(size: 8.5, weight: .heavy, tracking: 1.2, lineSpacingRatio: 1.2)
}

extension View {
    /// Applies one of the design's styles, including tracking and line spacing.
    func mbFont(_ style: MBTypography.Style) -> some View {
        self.font(style.font)
            .tracking(style.tracking)
            .lineSpacing(style.lineSpacing)
    }
}
