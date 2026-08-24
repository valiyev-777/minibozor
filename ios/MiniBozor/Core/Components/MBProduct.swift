import SwiftUI

/// Photo with the design's warm neutral backdrop showing through while it loads.
struct MBProductImage: View {
    let url: String?
    var cornerRadius: CGFloat = MB.metric.radiusXL
    var background: Color = MB.color.photoWarmAlt
    var contentMode: ContentMode = .fill

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
                }
            }
            .clipShape(RoundedRectangle(cornerRadius: cornerRadius, style: .continuous))
    }
}

/// `1 090 000` + `−29%` + struck-through old price.
struct MBPriceRow: View {
    let price: Int
    var oldPrice: Int?
    var discountPercent: Int?
    var style: MBTypography.Style = MB.type.price

    var body: some View {
        VStack(alignment: .leading, spacing: 1) {
            HStack(alignment: .lastTextBaseline, spacing: 6) {
                Text(Format.grouped(price)).mbFont(style).foregroundStyle(MB.color.ink)
                if let discountPercent {
                    Text("−\(discountPercent)%").mbFont(MB.type.micro).foregroundStyle(MB.color.danger)
                }
            }
            if let oldPrice, oldPrice > price {
                Text(Format.grouped(oldPrice))
                    .mbFont(MB.type.meta)
                    .strikethrough()
                    .foregroundStyle(MB.color.placeholder)
            }
        }
    }
}

struct MBRating: View {
    let rating: Double
    let reviewsCount: Int

    var body: some View {
        HStack(spacing: 4) {
            Text("★").mbFont(MB.type.meta).foregroundStyle(MB.color.star)
            Text(Format.rating(rating)).mbFont(MB.type.meta).foregroundStyle(MB.color.icon)
            if reviewsCount > 0 {
                Text("·").mbFont(MB.type.meta).foregroundStyle(MB.color.hairlineStrong)
                Text("\(reviewsCount) sharh").mbFont(MB.type.meta).foregroundStyle(MB.color.icon)
            }
        }
    }
}

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

struct FavoriteBubble: View {
    let isFavorite: Bool
    var size: CGFloat = 24
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            MBIcon(
                "heart",
                size: size * 0.5,
                tint: isFavorite ? MB.color.danger : MB.color.textSecondary,
                lineWidth: 2
            )
            .frame(width: size, height: size)
            .background(.white.opacity(0.92))
            .clipShape(Circle())
        }
        .buttonStyle(.plain)
    }
}

/// The two-per-row grid tile from the home screen and search results.
struct MBProductTile: View {
    let product: ProductCardDTO
    var onOpen: () -> Void
    var onToggleFavorite: () -> Void
    var onAddToCart: (() -> Void)?

    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            ZStack(alignment: .topTrailing) {
                MBProductImage(url: product.imageUrl)
                    .frame(height: MB.metric.tileImageHeight)
                    .overlay(alignment: .bottomLeading) {
                        if let badge = product.badge, !badge.isEmpty {
                            MBStatusPill(badge, background: MB.color.ink.opacity(0.8), contentColor: .white)
                                .padding(6)
                        }
                    }
                FavoriteBubble(isFavorite: product.isFavorite, action: onToggleFavorite)
                    .padding(6)
            }
            .contentShape(Rectangle())
            .onTapGesture(perform: onOpen)

            MBPriceRow(
                price: product.price,
                oldPrice: product.oldPrice,
                discountPercent: product.discountPercent
            )
            Text(product.title)
                .mbFont(MB.type.caption)
                .foregroundStyle(MB.color.inkSoft)
                .lineLimit(2)
                .frame(height: 30, alignment: .top)
            MBRating(rating: product.rating, reviewsCount: product.reviewsCount)

            if let onAddToCart {
                Button(action: onAddToCart) {
                    Text("Savatga")
                        .mbFont(MB.type.label)
                        .foregroundStyle(.white)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 9)
                        .background(MB.color.accent)
                        .clipShape(RoundedRectangle(cornerRadius: MB.metric.radiusM, style: .continuous))
                }
                .buttonStyle(.plain)
                .padding(.top, 3)
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
            VStack(alignment: .leading, spacing: 5) {
                MBProductImage(
                    url: product.imageUrl,
                    cornerRadius: MB.metric.radiusL,
                    background: MB.color.photoWarm
                )
                .frame(width: MB.metric.railTileWidth, height: MB.metric.railTileWidth)

                HStack(alignment: .lastTextBaseline, spacing: 5) {
                    Text(Format.grouped(product.price))
                        .mbFont(MB.type.priceSmall)
                        .foregroundStyle(MB.color.ink)
                    if let off = product.discountPercent {
                        Text("−\(off)%").mbFont(MB.type.micro).foregroundStyle(MB.color.danger)
                    }
                }
                Text(product.title)
                    .mbFont(MB.type.meta)
                    .foregroundStyle(MB.color.inkSoft)
                    .lineLimit(2)
                    .multilineTextAlignment(.leading)
                    .frame(height: 28, alignment: .top)
            }
            .frame(width: MB.metric.railTileWidth, alignment: .leading)
        }
        .buttonStyle(.plain)
    }
}

/// Wide "Bugungi tanlov" tile.
struct MBDealTile: View {
    let product: ProductCardDTO
    let onOpen: () -> Void

    var body: some View {
        Button(action: onOpen) {
            VStack(alignment: .leading, spacing: 5) {
                MBProductImage(url: product.imageUrl, cornerRadius: MB.metric.radiusL)
                    .frame(height: MB.metric.dealImageHeight)
                    .overlay(alignment: .topLeading) {
                        if let off = product.discountPercent {
                            MBStatusPill("−\(off)%", background: MB.color.danger, contentColor: .white)
                                .padding(6)
                        }
                    }
                MBPriceRow(price: product.price, oldPrice: product.oldPrice)
                Text(product.title)
                    .mbFont(MB.type.caption)
                    .foregroundStyle(MB.color.inkSoft)
                    .lineLimit(2)
                    .multilineTextAlignment(.leading)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .buttonStyle(.plain)
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
