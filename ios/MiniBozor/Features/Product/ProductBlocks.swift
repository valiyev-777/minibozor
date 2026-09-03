import SwiftUI

/// The rating, in the place the description used to have.
///
/// What someone wants at the top of a product page is not the seller's own
/// prose — it is what other buyers said, and how many of them there were. So
/// the panel leads with the number, the stars carry the fraction, and the
/// customers' own photographs sit beside it as the way through to the reviews.
/// The description still exists; it is further down, where a decided buyer goes
/// looking for it.
struct RatingPanel: View {
    let rating: Double
    let reviewsCount: Int
    var photos: [String] = []
    var photosTotal: Int = 0
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 10) {
                VStack(alignment: .leading, spacing: 5) {
                    HStack(spacing: 9) {
                        Text(Format.rating(rating))
                            .mbFont(MB.type.title1)
                            .foregroundStyle(MB.color.ink)
                        MBFractionalStars(rating: rating, size: 17)
                    }
                    // Reviews only. The order count used to sit here beside
                    // them, and the line below now prints what has sold as one
                    // half of its own answer — the same number twice in forty
                    // vertical points was one too many.
                    Text(LPlural("n_reviews", count: reviewsCount, "\(reviewsCount)"))
                        .mbFont(MB.type.caption)
                        .foregroundStyle(MB.color.textSecondary)
                        .lineLimit(1)
                }
                Spacer(minLength: 0)
                if photos.isEmpty {
                    MBIcon("chevron-right", size: 16, tint: MB.color.icon)
                } else {
                    MBReviewPhotoStack(photos: photos, total: photosTotal)
                }
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 12)
            .frame(maxWidth: .infinity)
            .overlay {
                RoundedRectangle(cornerRadius: MB.metric.radiusXL, style: .continuous)
                    .stroke(MB.color.border, lineWidth: 1)
            }
        }
        .buttonStyle(MBCardPressStyle(pressedScale: 0.99))
    }
}

/// Under this many left, the count stops being a fact and becomes a reason.
private let lowStock = 5

/// How many are left and how many have gone, in one line under the rating.
///
/// The same fact the tile in the grid prints, at the same weight and in the same
/// words — a caption with the box beside it, quiet by default and red once the
/// number has something to say. What it says fits on a line, so it takes a line.
///
/// The pill only appears when there is a reason for it. A product that is simply
/// in stock says so by not saying anything.
///
/// `stockLeft` and `inStock` are about the colour on show above, not about the
/// product as a whole — the photograph is of one colour, and the count under it
/// has to be the count of the thing being looked at.
struct ShelfLine: View {
    let stockLeft: Int
    let soldCount: Int
    let inStock: Bool

    private var gone: Bool { !inStock || stockLeft <= 0 }
    private var low: Bool { !gone && stockLeft <= lowStock }
    private var urgent: Bool { gone || low }

    var body: some View {
        HStack(spacing: 6) {
            MBIcon("box", size: 14, tint: urgent ? MB.color.danger : MB.color.icon)
            // Nothing to count when there are none: the pill on the right is
            // the whole of what a sold-out shelf has to say, and "0 dona qoldi"
            // beside it would be the same sentence twice.
            if !gone {
                Text(String(format: L("n_dona_qoldi"), stockLeft))
                    .mbFont(MB.type.caption)
                    .foregroundStyle(low ? MB.color.danger : MB.color.inkMuted)
                    .lineLimit(1)
            }
            if soldCount > 0 {
                if !gone {
                    Text("·")
                        .mbFont(MB.type.caption)
                        .foregroundStyle(MB.color.hairlineStrong)
                }
                Text(LPlural("n_sotilgan", count: soldCount, Format.grouped(soldCount)))
                    .mbFont(MB.type.caption)
                    .foregroundStyle(MB.color.textSecondary)
                    .lineLimit(1)
            }
            Spacer(minLength: 0)
            if urgent {
                MBStatusPill(
                    L(gone ? "tugadi" : "kam_qoldi"),
                    background: MB.color.dangerBg,
                    contentColor: MB.color.danger
                )
            }
        }
        .frame(maxWidth: .infinity)
    }
}

/// `Rang: Oqish rang` — the label the pickers share.
struct PickerLabel: View {
    let name: String
    let value: String
    var action: String?
    var onAction: (() -> Void)?

    var body: some View {
        HStack(spacing: 6) {
            Text("\(name):")
                .mbFont(MB.type.body)
                .foregroundStyle(MB.color.textSecondary)
            Text(value)
                .mbFont(MB.type.bodyBold)
                .foregroundStyle(MB.color.ink)
                .lineLimit(1)
            Spacer(minLength: 0)
            if let action, let onAction {
                Button(action: onAction) {
                    Text(action)
                        .mbFont(MB.type.label)
                        .foregroundStyle(MB.color.accent)
                        .lineLimit(1)
                }
                .buttonStyle(.plain)
            }
        }
    }
}

/// The colours, as photographs of the thing in that colour.
///
/// A hex circle asks the customer to imagine what `#0E0F12` looks like on a
/// shoe; the photograph shows them. Where the shop supplied no photo for a
/// colour the tile falls back to the swatch, so a half-photographed catalogue
/// still picks.
struct ColorOptionsRow: View {
    let colors: [VariantDTO]
    let selectedId: Int?
    /// Used for the fallback when a lone colour has no photo of its own.
    var productImages: [String] = []
    let onSelect: (Int) -> Void

    private var selected: VariantDTO? {
        colors.first { $0.id == selectedId } ?? colors.first
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            PickerLabel(name: L("rang"), value: selected?.label ?? "")
            Spacer().frame(height: 12)
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 10) {
                    ForEach(Array(colors.enumerated()), id: \.element.id) { index, color in
                        let isSelected = color.id == selected?.id
                        // One colour and no photo of its own: the product's own
                        // first photograph is a picture of it in that colour.
                        let photo = color.imageUrl
                            ?? (colors.count == 1 ? productImages.first : nil)
                        Button {
                            onSelect(color.id)
                        } label: {
                            Group {
                                if let photo {
                                    MBProductImage(url: photo, cornerRadius: MB.metric.radiusL)
                                } else {
                                    Rectangle()
                                        .fill(Color(hexString: color.value,
                                                    fallback: MB.color.fill))
                                        .clipShape(RoundedRectangle(
                                            cornerRadius: MB.metric.radiusL,
                                            style: .continuous
                                        ))
                                }
                            }
                            // Room for the ring to read as a ring rather than as
                            // a dark edge on the photograph.
                            .padding(isSelected ? 4 : 3)
                            .frame(width: 74, height: 74)
                            .overlay {
                                RoundedRectangle(cornerRadius: MB.metric.radiusXL,
                                                 style: .continuous)
                                    .stroke(
                                        isSelected ? MB.color.ink : MB.color.border,
                                        lineWidth: isSelected ? 2 : 1
                                    )
                            }
                            .opacity(color.inStock ? 1 : 0.4)
                            .id(index)
                        }
                        .buttonStyle(MBCardPressStyle(pressedScale: 0.95))
                        .disabled(!color.inStock)
                    }
                }
                .padding(.vertical, 1)
            }
        }
    }
}

/// The sizes, with the selected one ringed rather than filled.
///
/// One row that scrolls, not a block that wraps. A size run is a single scale —
/// 39 through 46 — and wrapping it put 46 alone on a second line, which reads as
/// a separate question rather than as the end of the same one.
struct SizeOptionsRow: View {
    let sizes: [VariantDTO]
    let selectedId: Int?
    var onOpenChart: (() -> Void)?
    let onSelect: (Int) -> Void

    private var selected: VariantDTO? { sizes.first { $0.id == selectedId } }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            PickerLabel(
                name: L("olcham"),
                value: selected?.label ?? "",
                action: onOpenChart == nil ? nil : L("olchamlar_jadvali"),
                onAction: onOpenChart
            )
            Spacer().frame(height: 12)
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 5) {
                    ForEach(sizes) { variant in
                        MBSizeChip(
                            variant.label,
                            selected: variant.id == selected?.id,
                            enabled: variant.inStock
                        ) {
                            onSelect(variant.id)
                        }
                    }
                }
                .padding(.vertical, 1)
            }
        }
    }
}
