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
    /// The product card's own corner, a step rounder than `radiusXL`.
    ///
    /// Rounder reads as softer, which is the point of the card having lost its
    /// border: 18 against the tile's 14 keeps the photograph inside it roughly
    /// concentric at the card's 8 pt of padding.
    let radiusTile: CGFloat = 18

    let buttonHeight: CGFloat = 48
    let fieldHeight: CGFloat = 48
    let searchHeight: CGFloat = 38
    let bannerHeight: CGFloat = 146
    let tabBarHeight: CGFloat = 70
    let tabBarInset: CGFloat = 14

    /// Product photographs are square everywhere.
    ///
    /// The catalogue is shot 1:1 with its own baked-in backdrop, so a tile of
    /// any other ratio shows a letterboxed strip of its own ground down two
    /// sides. The old fixed heights (148 for a grid tile, 104 for a deal tile)
    /// did exactly that, and left the two kinds of card cropping differently.
    let railTileWidth: CGFloat = 112
    let categoryTile: CGFloat = 44

    /// How far a product card is lifted off whatever it sits on.
    ///
    /// The cards used to be bare columns with nothing around them at all; a
    /// shadow this shallow groups a card without drawing an edge, and reads on
    /// the grey canvas of a listing and the white panel of the home page alike.
    /// Nothing is drawn on the dark appearance, where the card is separated by
    /// being a step lighter than its ground instead.
    let cardLift: CGFloat = 3
}

/// One namespace for the whole design system, so screens read
/// `MB.color.accent`, `MB.type.title1`, `MB.metric.gutter`.
enum MB {
    static let color = MBColors()
    static let type = MBTypography()
    static let metric = MBMetrics()
}
