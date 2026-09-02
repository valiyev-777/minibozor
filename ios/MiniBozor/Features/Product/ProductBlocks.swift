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
    let soldCount: Int
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
                    HStack(spacing: 5) {
                        Text(LPlural("n_reviews", count: reviewsCount, "\(reviewsCount)"))
                            .mbFont(MB.type.caption)
                            .foregroundStyle(MB.color.textSecondary)
                            .lineLimit(1)
                        if soldCount > 0 {
                            Text("·")
                                .mbFont(MB.type.caption)
                                .foregroundStyle(MB.color.hairlineStrong)
                            Text(LPlural("n_orders", count: soldCount,
                                         Format.grouped(soldCount)))
                                .mbFont(MB.type.caption)
                                .foregroundStyle(MB.color.textSecondary)
                                .lineLimit(1)
                        }
                    }
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

/// "1 240 kishi sotib oldi" — the quiet nudge under the rating.
struct SoldLine: View {
    let soldCount: Int

    var body: some View {
        HStack(spacing: 7) {
            MBIcon("cart", size: 16, tint: MB.color.accent)
            Text(LPlural("n_buyers", count: soldCount, Format.grouped(soldCount)))
                .mbFont(MB.type.caption)
                .foregroundStyle(MB.color.textSecondary)
                .lineLimit(1)
        }
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
