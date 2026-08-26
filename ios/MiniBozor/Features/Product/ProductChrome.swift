import SwiftUI

/// The photo, and the bar that floats over it.
///
/// Both are driven by the scroll rather than playing on their own: the picture
/// closes away behind the page, and the bar takes the product's name over as
/// the page lets go of it.
enum ProductHero {
    /// Square, matching the photographs.
    ///
    /// A frame taller than the photo is wide leaves a band of frame down each
    /// side of a fitted picture, and two near-identical lights with a seam
    /// between them read as a mistake rather than a margin.
    static var height: CGFloat { UIScreen.main.bounds.width + chromeHeight }

    /// The bar: the status bar inset plus the row of buttons under it.
    static var chromeHeight: CGFloat { statusBarInset + 56 }

    static var statusBarInset: CGFloat {
        UIApplication.shared.connectedScenes
            .compactMap { ($0 as? UIWindowScene)?.keyWindow?.safeAreaInsets.top }
            .first ?? 44
    }

    /// The scroll coordinate space the hero and the bar measure themselves in.
    static let space = "product.scroll"
}

struct ProductHeroView: View {
    let images: [String]
    let badge: String?
    /// 0 while the photo fills the top, 1 once it has closed away behind.
    let closed: CGFloat

    @State private var page = 0

    var body: some View {
        ZStack(alignment: .top) {
            // Light in both appearances, and the same white the photographs are
            // shot on, so the inset below reads as breathing room rather than
            // as a panel with edges.
            MB.color.photoStudio

            TabView(selection: $page) {
                ForEach(Array(images.enumerated()), id: \.offset) { offset, url in
                    MBProductImage(url: url, cornerRadius: 0, background: MB.color.photoStudio)
                        .padding(.horizontal, 18)
                        .padding(.vertical, 10)
                        .tag(offset)
                }
            }
            .tabViewStyle(.page(indexDisplayMode: .never))
            // Below the bar, not under it: the frame is a square of photo plus
            // the bar's own height, so the whole picture is in the clear.
            .padding(.top, ProductHero.chromeHeight)
            .opacity(1 - closed)
            .scaleEffect(1 - 0.06 * closed)
            // Holds back at a third of the scroll, so it reads as closing
            // behind the page rather than being pushed off the top.
            .offset(y: closed * ProductHero.height * 0.30)

            if let badge {
                MBStatusPill(badge, background: MB.color.scrim, contentColor: MB.color.onScrim)
                    .padding(.leading, 16)
                    .padding(.top, ProductHero.chromeHeight + 8)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .opacity(1 - closed)
            }

            if images.count > 1 {
                HStack(spacing: 5) {
                    ForEach(images.indices, id: \.self) { index in
                        Capsule()
                            .fill(index == page ? MB.color.ink : MB.color.hairlineStrong)
                            .frame(width: index == page ? 18 : 6, height: 6)
                            .animation(.spring(response: 0.3, dampingFraction: 0.8), value: page)
                    }
                }
                .frame(maxHeight: .infinity, alignment: .bottom)
                .padding(.bottom, 18)
                .opacity(1 - closed)
            }
        }
        .frame(height: ProductHero.height)
        .clipped()
    }
}

/// The bar over the photo.
///
/// The buttons never move: they sit on the picture to begin with and stay in
/// exactly the same place once the bar has a surface behind it. What changes is
/// underneath them — the name and price slide down into the row the photo has
/// vacated, so nothing about the product is ever off screen.
struct ProductChromeView: View {
    let product: ProductDTO?
    /// How far the name has been handed from the page to this bar, 0…1.
    let handover: CGFloat
    let onBack: () -> Void
    let onToggleFavorite: () -> Void
    let onShare: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 10) {
                GlassButton(glyph: "arrow-left", action: onBack)
                Spacer(minLength: 0)
                if let product {
                    GlassButton(
                        glyph: "heart",
                        tint: product.isFavorite ? MB.color.danger : MB.color.ink,
                        action: onToggleFavorite
                    )
                    GlassButton(glyph: "share", action: onShare)
                }
            }
            .frame(height: 36)

            if let product {
                HStack(spacing: 14) {
                    // The price is measured at whatever width its digits need
                    // and the name takes what is left, so a name of any length
                    // cannot squeeze the price and a price of any size cannot
                    // reach the name.
                    Text(product.title)
                        .mbFont(MB.type.title1)
                        .foregroundStyle(MB.color.ink)
                        .lineLimit(1)
                        .frame(maxWidth: .infinity, alignment: .leading)
                    MBPriceRow(price: product.price, style: MB.type.title2)
                        .fixedSize(horizontal: true, vertical: false)
                }
                .padding(.top, 10)
                .opacity(handover)
                .offset(y: (handover - 1) * 14)
            }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 10)
        .padding(.top, ProductHero.statusBarInset)
        // An opaque ground first, then the page's surface faded over it.
        // Cross-fading two translucent layers never adds up to opaque in
        // between, and a quarter of the card behind would show through — which
        // is how the product's name ends up on screen twice.
        .background {
            ZStack {
                MB.color.photoStudio
                MB.color.surface.opacity(handover)
            }
            .ignoresSafeArea(edges: .top)
        }
    }
}

/// A circular button legible on a photograph and on a plain surface alike.
private struct GlassButton: View {
    let glyph: String
    var tint: Color = MB.color.ink
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            MBIcon(glyph, size: 18, tint: tint, lineWidth: 1.9)
                .frame(width: 36, height: 36)
                .background(MB.color.fill)
                .clipShape(Circle())
        }
        .buttonStyle(.plain)
    }
}

/// The rail at the foot of the page, with chips over it.
///
/// Two readings of the same set rather than two requests: what the catalogue
/// considers similar, and the same list by how much people have reviewed it.
/// A genuine "recently viewed" needs a view history the app does not keep yet.
struct RecommendationsRail: View {
    let products: [ProductCardDTO]
    let onOpen: (Int) -> Void

    @State private var tab = 0

    private var ordered: [ProductCardDTO] {
        tab == 0 ? products : products.sorted { $0.reviewsCount > $1.reviewsCount }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            SectionHeader(title: L("oxshash_tovarlar")).padding(.horizontal, 16)
            Spacer().frame(height: 10)
            HStack(spacing: 8) {
                MBChip(L("oxshash"), selected: tab == 0) { tab = 0 }
                MBChip(L("ommabop"), selected: tab == 1) { tab = 1 }
            }
            .padding(.horizontal, 16)
            Spacer().frame(height: 14)
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(alignment: .top, spacing: 10) {
                    ForEach(ordered) { item in
                        MBRailTile(product: item) { onOpen(item.id) }
                    }
                }
                .padding(.horizontal, 16)
            }
        }
        .padding(.top, 6)
    }
}
