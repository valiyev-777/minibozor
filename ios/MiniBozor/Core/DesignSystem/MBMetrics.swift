import SwiftUI

/// Spacing, radii and component sizes from `design/tokens.json`.
///
/// The design is drawn at 375 pt wide, which is close enough to a real device
/// that these are used as-is rather than scaled.
struct MBMetrics {
    let gutter: CGFloat = 20
    let cardGutter: CGFloat = 12
    let cardPad: CGFloat = 14
    let sectionPad: CGFloat = 16

    let gapXS: CGFloat = 4
    let gapS: CGFloat = 6
    let gapM: CGFloat = 10
    let gapL: CGFloat = 12
    let gapXL: CGFloat = 16

    let radiusXS: CGFloat = 6
    let radiusS: CGFloat = 8
    let radiusM: CGFloat = 12
    let radiusL: CGFloat = 13
    let radiusXL: CGFloat = 14
    let radiusXXL: CGFloat = 20
    let radiusSheet: CGFloat = 24

    let buttonHeight: CGFloat = 48
    let fieldHeight: CGFloat = 48
    let searchHeight: CGFloat = 38
    let bannerHeight: CGFloat = 146
    let tabBarHeight: CGFloat = 70
    let tabBarInset: CGFloat = 14

    let tileImageHeight: CGFloat = 148
    let railTileWidth: CGFloat = 112
    let dealImageHeight: CGFloat = 104
    let categoryTile: CGFloat = 44
}

/// One namespace for the whole design system, so screens read
/// `MB.color.accent`, `MB.type.title1`, `MB.metric.gutter`.
enum MB {
    static let color = MBColors()
    static let type = MBTypography()
    static let metric = MBMetrics()
}
