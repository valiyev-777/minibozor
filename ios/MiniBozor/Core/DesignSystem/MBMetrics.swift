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
    /// How wide a rail tile is, so a rail always shows two and a half of them.
    ///
    /// A hard 112 was drawn against a 375 pt canvas and never did fit three
    /// tiles anywhere: three of them and their gaps come to 356, and the widest
    /// device in the design is 319 of room. What that produced was two and
    /// three quarter cards — near enough to three to read as three cards that
    /// would not fit, rather than as a rail that scrolls.
    ///
    /// Two and a half is the point of the number: half a card is unmistakably
    /// half a card, so the rail says it continues without a chevron to say it,
    /// and a bigger phone gets a roomier card rather than a wider gap.
    ///
    /// Sized against the home rail: 20 pt of padding before the first tile and
    /// after the last, and 10 between them. Clamped at both ends — a 320 pt
    /// phone would shrink the photograph past what a photograph is for, and an
    /// iPad would blow one tile up instead of showing more of them.
    /// What a rail spends before its first tile, and after its last.
    let railEdge: CGFloat = 20

    var railTileWidth: CGFloat {
        let screen = UIScreen.main.bounds.width
        return min(max((screen - 40 - 20) / 2.5, 108), 150)
    }

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
