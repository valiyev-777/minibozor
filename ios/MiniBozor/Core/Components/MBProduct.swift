import SwiftUI

/// Photo with the design's warm neutral backdrop showing through while it loads.
struct MBProductImage: View {
    let url: String?
    var cornerRadius: CGFloat = MB.metric.radiusXL
    var background: Color = MB.color.photoWarmAlt
    /// Fit, not fill: catalogue photos are cut-outs in mixed ratios, and
    /// filling a square tile with a 387x516 shoe shows its middle and neither
    /// end. Scene photography — the home banner — asks for `.fill`.
    var contentMode: ContentMode = .fit

    var body: some View {
        Rectangle()
            .fill(background)
            .overlay {
                if let url, let parsed = AppConfig.media(url) {
                    AsyncImage(url: parsed) { phase in
                        if let image = phase.image {
                            image.resizable().aspectRatio(contentMode: contentMode)
                        } else {
                            Color.clear
                        }
                    }
                } else {
                    // No photo supplied. A muted glyph reads as "none" where an
                    // empty warm rectangle just reads as broken.
                    MBIcon("box", size: 26, tint: MB.color.hairlineStrong)
                }
            }
            .clipShape(RoundedRectangle(cornerRadius: cornerRadius, style: .continuous))
    }
}

/// The card every product tile sits in: a soft surface, lifted a little, with
/// nothing drawn around it.
///
/// The tiles used to be bare columns of photo, price and title separated by
/// nothing but a gap, which left the reader doing the grouping — two photos side
/// by side with four lines of text under them, and which price belongs to which
/// shoe is a guess. A hairline box would answer it, but eight boxes in a grid
/// is eight hard edges between the customer and the photographs.
///
/// So the grouping is done by lift: a surface a step off its ground with a
/// shallow shadow under it, and a corner rounder than a bordered card could
/// carry. On the dark appearance, where a black shadow is invisible, the card is
/// a step lighter than the page instead — `fill` rather than `surface`, because
/// `surfaceAlt` is four values above the panel the home page puts these on,
/// which is not a step anybody can see.
struct MBProductCardStyle: ViewModifier {
    var cornerRadius: CGFloat = MB.metric.radiusTile

    @Environment(\.colorScheme) private var scheme

    func body(content: Content) -> some View {
        content
            .background(scheme == .dark ? MB.color.fill : MB.color.surface)
            .clipShape(RoundedRectangle(cornerRadius: cornerRadius, style: .continuous))
            .shadow(
                color: .black.opacity(scheme == .dark ? 0 : 0.10),
                radius: MB.metric.cardLift * 2,
                x: 0,
                y: MB.metric.cardLift * 0.6
            )
    }
}

extension View {
    func mbProductCard(cornerRadius: CGFloat = MB.metric.radiusTile) -> some View {
        modifier(MBProductCardStyle(cornerRadius: cornerRadius))
    }
}

/// The saving, in the red pill this app puts a discount in everywhere.
///
/// One view rather than the same six lines in four places — the tile, the rail,
/// the product page's own price and the bar at the top of it had drifted apart
/// by a padding already. The font is set directly rather than through `mbFont`
/// so the label style's 1.4 pt of tracking is left out: on a four-glyph token it
/// spaced `−9%` out into `− 9 %`, which reads as three marks instead of one
/// number.
struct MBDiscountPill: View {
    let percent: Int
    /// A step up for the product page, where the price is the largest thing.
    var large = false

    var body: some View {
        Text("−\(percent)%")
            .font(large ? MB.type.label.font : MB.type.captionBold.font)
            .tracking(0)
            .foregroundStyle(MB.color.danger)
            .lineLimit(1)
            .padding(.horizontal, large ? 9 : 6)
            .padding(.vertical, large ? 5 : 3)
            .background(MB.color.dangerBg)
            .clipShape(RoundedRectangle(cornerRadius: MB.metric.radiusS, style: .continuous))
    }
}

/// What it costs, and what that is off: `1 090 000` on its own line, then
/// `1 540 000  −29%` under it.
///
/// Two lines, not one. Beside the number the pill did not fit: a card in a
/// two-per-row grid has about 150 pt of text width, `168 000 000` takes 110 of
/// them at price weight, and the pill needs 40 more — so the two were pressed
/// against each other and on the longest prices the number itself was clipped.
/// They are also two different kinds of fact: what the thing costs is the
/// headline, what it used to cost and how much is off is the footnote, and a
/// footnote belongs under the line it annotates.
///
/// The footnote line is held even when there is nothing to say, so a discounted
/// card and a full-price one beside it are the same height — a grid lays two
/// cards side by side and neither stretches to the other.
struct MBPriceRow: View {
    let price: Int
    var oldPrice: Int?
    var discountPercent: Int?
    var style: MBTypography.Style = MB.type.price
    /// Off for the bars and rows that are not in a grid and need no reserved
    /// footnote.
    var reservesFootnote = true

    private var was: Int? {
        guard let oldPrice, oldPrice > price else { return nil }
        return oldPrice
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(Format.grouped(price))
                .mbFont(style)
                .foregroundStyle(MB.color.ink)
                .lineLimit(1)

            if was != nil || discountPercent != nil || reservesFootnote {
                HStack(spacing: 6) {
                    if let was {
                        Text(Format.grouped(was))
                            .font(MB.type.meta.font)
                            .foregroundStyle(MB.color.textQuaternary)
                            .strikethrough()
                            .lineLimit(1)
                    }
                    if let discountPercent {
                        MBDiscountPill(percent: discountPercent)
                    }
                }
                .frame(minHeight: reservesFootnote ? 20 : 0, alignment: .leading)
            }
        }
    }
}

/// Five stars, filled to a whole number.
struct MBStars: View {
    let rating: Int
    var size: CGFloat = 13

    var body: some View {
        HStack(spacing: 1) {
            ForEach(0..<5, id: \.self) { index in
                Text("★")
                    .font(.system(size: size))
                    .foregroundStyle(index < rating ? MB.color.star : MB.color.divider)
            }
        }
    }
}

/// The same five stars, but a 4.3 shows four gold and a third of the fifth.
///
/// Rounding to four loses the very thing the number is for — the difference
/// between a 4.0 and a 4.4 is most of what a rating says — so the partial star
/// is a gold row masked to the fraction, over a grey one.
struct MBFractionalStars: View {
    let rating: Double
    var size: CGFloat = 15

    private var fill: Double { min(max(rating / 5, 0), 1) }

    private var row: some View {
        HStack(spacing: size * 0.1) {
            ForEach(0..<5, id: \.self) { _ in
                Text("★").font(.system(size: size))
            }
        }
    }

    var body: some View {
        row
            .foregroundStyle(MB.color.divider)
            .overlay(alignment: .leading) {
                GeometryReader { geometry in
                    row
                        .foregroundStyle(MB.color.star)
                        .frame(width: geometry.size.width, alignment: .leading)
                        .mask(alignment: .leading) {
                            Rectangle().frame(width: geometry.size.width * fill)
                        }
                }
            }
    }
}

/// The overlapping strip of customer photographs beside a rating.
///
/// The last tile carries "+N" for everything the strip has no room for, which is
/// also the tap target's promise: there are more of these, and they are through
/// here. Drawn overlapping rather than spaced, so three tiles read as a stack of
/// many rather than as three separate pictures.
struct MBReviewPhotoStack: View {
    let photos: [String]
    let total: Int
    var tile: CGFloat = 46
    var shown = 3

    var body: some View {
        let strip = Array(photos.prefix(shown))
        let more = total - strip.count
        HStack(spacing: -tile * 0.22) {
            ForEach(Array(strip.enumerated()), id: \.offset) { offset, photo in
                MBProductImage(
                    url: photo,
                    cornerRadius: MB.metric.radiusS,
                    contentMode: .fill
                )
                .frame(width: tile - 3, height: tile - 3)
                .overlay {
                    if offset == strip.count - 1, more > 0 {
                        ZStack {
                            MB.color.scrim
                            Text("+\(more)")
                                .mbFont(MB.type.label)
                                .foregroundStyle(MB.color.onScrim)
                        }
                        .clipShape(RoundedRectangle(cornerRadius: MB.metric.radiusS,
                                                    style: .continuous))
                    }
                }
                // A ring of the panel's own surface, so the tiles read as
                // separate cards where they overlap.
                .padding(1.5)
                .background(MB.color.surface)
                .clipShape(RoundedRectangle(cornerRadius: MB.metric.radiusL, style: .continuous))
            }
        }
    }
}

/// The heart on a photograph.
///
/// `size` is the disc that is seen; `margin` is transparent room around it that
/// belongs to the tap target, so a 28 pt bubble is a 44 pt thing to hit. It used
/// to be a bare 24 pt circle — a target smaller than a fingertip, in the corner
/// of a card that is itself tappable, so a miss opened the product instead of
/// saving it. The disc carries a shallow lift rather than sitting at 92% white:
/// half the catalogue is photographed against a pale studio backdrop, and a
/// white circle on off-white had to be looked for. Nothing is drawn on the dark
/// appearance, where a white disc needs no help being seen.
struct FavoriteBubble: View {
    let isFavorite: Bool
    var size: CGFloat = 28
    var margin: CGFloat = 8
    let action: () -> Void

    @Environment(\.colorScheme) private var scheme

    var body: some View {
        Button(action: action) {
            MBIcon(
                "heart",
                size: size * 0.5,
                tint: isFavorite ? MB.color.danger : MB.color.textSecondary,
                lineWidth: 2
            )
            .frame(width: size, height: size)
            .background(.white)
            .clipShape(Circle())
            .shadow(color: .black.opacity(scheme == .dark ? 0 : 0.16), radius: 3, y: 1)
            .padding(margin)
            .contentShape(Circle())
        }
        .buttonStyle(MBCardPressStyle(pressedScale: 0.9))
    }
}

/// Add to cart, at the end of the card's own last line.
///
/// It has been three things. A full-width blue bar across the foot of every card
/// — a lot of blue in a grid of eight, and a whole row of card height spent on
/// the secondary action, the primary one being to open the product. Then a disc
/// on the photograph, which was handy and looked like a sticker somebody had put
/// on the picture. This is the third: a plain accent disc beside the name,
/// sharing the two lines the name already occupies, so it costs the card no
/// height and sits on the card's own surface rather than on the seller's
/// photograph.
///
/// No flourish on it. The feedback is the same dip every card makes under a
/// finger — a glyph that flipped to a tick would claim more than the tap knows,
/// since on a product with sizes it opens the picker instead of adding anything.
struct MBCartButton: View {
    var size: CGFloat = 34
    var margin: CGFloat = 5
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            MBIcon("cart", size: size * 0.47, tint: .white, lineWidth: 2)
                .frame(width: size, height: size)
                .background(MB.color.accent)
                .clipShape(Circle())
                .padding(margin)
                .contentShape(Circle())
        }
        .buttonStyle(MBCardPressStyle(pressedScale: 0.9))
    }
}

/// The two-per-row grid tile from the home screen and search results: a square
/// photograph with the heart in one corner, then the price, then the name with
/// the cart at the end of it.
struct MBProductTile: View {
    let product: ProductCardDTO
    var onOpen: () -> Void
    var onToggleFavorite: () -> Void
    var onAddToCart: (() -> Void)?

    var body: some View {
        ProductTileBody(
            product: product,
            onOpen: onOpen,
            onToggleFavorite: onToggleFavorite,
            onAddToCart: onAddToCart
        )
    }
}

/// Wide "Bugungi tanlov" tile: the same card without the corner controls.
struct MBDealTile: View {
    let product: ProductCardDTO
    let onOpen: () -> Void

    var body: some View {
        ProductTileBody(product: product, onOpen: onOpen)
    }
}

/// The card itself: a square photograph, then what it costs, then what it is.
///
/// Three things, and nothing else. No rating and no review count: a star and
/// "12 sharh" on every tile of a grid is a row of numbers nobody compares —
/// what a rating is for is the product page, where there is a panel of them and
/// the reviews themselves are a tap away.
///
/// The card is a button and the two controls are overlaid on top of it rather
/// than nested inside, because a button inside a button never sees the tap.
private struct ProductTileBody: View {
    let product: ProductCardDTO
    let onOpen: () -> Void
    var onToggleFavorite: (() -> Void)?
    var onAddToCart: (() -> Void)?

    var body: some View {
        Button(action: onOpen) {
            VStack(alignment: .leading, spacing: 0) {
                MBProductImage(url: product.imageUrl, cornerRadius: MB.metric.radiusL)
                    // Square, always: the catalogue is shot 1:1 with its own
                    // backdrop, so any other ratio letterboxes the tile.
                    .aspectRatio(1, contentMode: .fit)
                    .overlay(alignment: .bottomLeading) {
                        if let badge = product.badge, !badge.isEmpty {
                            MBStatusPill(
                                badge,
                                background: MB.color.scrim,
                                contentColor: MB.color.onScrim
                            )
                            .padding(6)
                        }
                    }

                Spacer().frame(height: 9)
                // Full width, always: the price is the one line on the card that
                // must never be squeezed, so nothing shares its row.
                MBPriceRow(
                    price: product.price,
                    oldPrice: product.oldPrice,
                    discountPercent: product.discountPercent
                )
                Spacer().frame(height: 6)

                HStack(spacing: 0) {
                    // Set at reading size, not at 11 pt. A product name in a
                    // two-up grid is the one thing on the card that has to be
                    // read rather than recognised.
                    Text(product.title)
                        .mbFont(MB.type.body)
                        .foregroundStyle(MB.color.inkSoft)
                        .lineLimit(2)
                        .multilineTextAlignment(.leading)
                        .frame(maxWidth: .infinity, minHeight: 38, alignment: .topLeading)
                    // The room the cart disc occupies, held open in the label so
                    // the name never runs under it.
                    if onAddToCart != nil {
                        Color.clear.frame(width: 40, height: 1)
                    }
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(8)
            .mbProductCard()
        }
        .buttonStyle(MBCardPressStyle())
        .overlay(alignment: .topTrailing) {
            if let onToggleFavorite {
                FavoriteBubble(isFavorite: product.isFavorite, action: onToggleFavorite)
            }
        }
        .overlay(alignment: .bottomTrailing) {
            if let onAddToCart {
                MBCartButton(action: onAddToCart).padding(.trailing, 3).padding(.bottom, 3)
            }
        }
    }
}

/// The 112 pt tile used by the horizontal rails.
struct MBRailTile: View {
    let product: ProductCardDTO
    let onOpen: () -> Void

    var body: some View {
        Button(action: onOpen) {
            VStack(alignment: .leading, spacing: 0) {
                MBProductImage(
                    url: product.imageUrl,
                    cornerRadius: MB.metric.radiusL,
                    background: MB.color.photoWarm
                )
                .frame(width: MB.metric.railTileWidth, height: MB.metric.railTileWidth)

                Spacer().frame(height: 8)
                // The same block the grid tile uses, a size down. It used to be
                // a row of its own making — the price and 9.5 pt of red text
                // side by side — which on a 112 pt card meant a nine-figure
                // price and a percentage fighting over 98 pt of it.
                MBPriceRow(
                    price: product.price,
                    discountPercent: product.discountPercent,
                    style: MB.type.priceSmall
                )
                Spacer().frame(height: 4)
                // A step up from meta: the rail is narrow, so a name gets two
                // short lines and needs both to be readable.
                Text(product.title)
                    .mbFont(MB.type.caption)
                    .foregroundStyle(MB.color.inkSoft)
                    .lineLimit(2)
                    .multilineTextAlignment(.leading)
                    .frame(height: 30, alignment: .top)
            }
            .frame(width: MB.metric.railTileWidth, alignment: .leading)
            .padding(7)
            .mbProductCard(cornerRadius: MB.metric.radiusXL)
        }
        .buttonStyle(MBCardPressStyle())
    }
}

/// Compact line item: photo, title, variant, price — cart, orders, reviews.
struct MBLineItem<Trailing: View>: View {
    let title: String
    let imageUrl: String?
    var meta: String = ""
    let price: Int
    var quantity: Int?
    var onTap: (() -> Void)?
    @ViewBuilder var trailing: Trailing

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            MBProductImage(url: imageUrl, cornerRadius: MB.metric.radiusL)
                .frame(width: 64, height: 64)
            VStack(alignment: .leading, spacing: 3) {
                Text(title).mbFont(MB.type.caption).foregroundStyle(MB.color.inkSoft).lineLimit(2)
                if !meta.isEmpty {
                    Text(meta).mbFont(MB.type.meta).foregroundStyle(MB.color.icon).lineLimit(1)
                }
                HStack(spacing: 6) {
                    Text(Format.grouped(price))
                        .mbFont(MB.type.priceSmall)
                        .foregroundStyle(MB.color.ink)
                    if let quantity {
                        Text("× \(quantity)").mbFont(MB.type.meta).foregroundStyle(MB.color.icon)
                    }
                }
            }
            Spacer(minLength: 0)
            trailing
        }
        .contentShape(Rectangle())
        .onTapGesture { onTap?() }
    }
}

extension MBLineItem where Trailing == EmptyView {
    init(
        title: String,
        imageUrl: String?,
        meta: String = "",
        price: Int,
        quantity: Int? = nil,
        onTap: (() -> Void)? = nil
    ) {
        self.init(
            title: title, imageUrl: imageUrl, meta: meta,
            price: price, quantity: quantity, onTap: onTap
        ) { EmptyView() }
    }
}
