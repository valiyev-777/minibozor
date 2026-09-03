import SwiftUI

/// The photo, and the bar that floats over it.
///
/// Both are driven by the scroll rather than playing on their own: the picture
/// is covered by the page climbing over it, and the bar grows its own surface at
/// the moment the page reaches it.
enum ProductHero {
    /// Square, matching the photographs, and running to the very top of the
    /// screen.
    ///
    /// Every catalogue photo is 1:1, so a square frame has nothing left over to
    /// show. It used to be a square *plus* the bar's height, which left a band
    /// of plain ground across the top with the buttons floating on it; the
    /// picture reaches the top of the screen now and the bar sits on it.
    static var height: CGFloat { UIScreen.main.bounds.width }

    /// The bar: the status bar inset plus the row of buttons under it.
    ///
    /// 64 is the row itself — a 44 pt button with 10 pt of air above and below.
    /// Shared with the page, which decides when the panel has crossed under the
    /// bar off the same number.
    static var chromeHeight: CGFloat { statusBarInset + 64 }

    static var statusBarInset: CGFloat {
        UIApplication.shared.connectedScenes
            .compactMap { ($0 as? UIWindowScene)?.keyWindow?.safeAreaInsets.top }
            .first ?? 44
    }

    /// The scroll coordinate space the hero and the bar measure themselves in.
    static let space = "product.scroll"

    /// How opaque the bar's own surface is, for a given crossing of the page
    /// under it.
    ///
    /// Brought up steeply, so it covers the wash as it arrives: cross-fading two
    /// grounds never adds up to opaque in between — at halfway a pair covers
    /// 0.75, and the wash showed through as a grey band sliding down the
    /// picture.
    static func barCover(_ crossing: CGFloat) -> CGFloat { min(crossing * 8, 1) }
}

/// The photograph at the top of the page.
///
/// It does not slide away as the page scrolls: it holds back at a fraction of
/// the scroll and is covered by the panel climbing over it, so it reads as being
/// covered where it stands rather than being pushed off the top. Nothing fades —
/// a transparent photograph shows the page's own ground through it, which on the
/// light appearance is a white band across the top of the screen.
struct ProductHeroView: View {
    let images: [String]
    let badge: String?
    /// 0 while the photo fills the top, 1 once the page has covered it.
    let closed: CGFloat
    /// Points the photo hangs back from the scroll, so the page's own panels are
    /// seen crossing in front of it.
    let lag: CGFloat
    /// Tapping the photograph opens it full screen: the page being shown, and
    /// the frame it is sitting in, so the full-screen view can grow out of it.
    let onOpen: (Int, CGRect) -> Void
    /// Hoisted, so the page above shares the photograph being shown: swiping
    /// the hero is how a colour gets chosen.
    @Binding var page: Int

    /// Where the live photograph sits on the screen, for the full-screen view to
    /// grow out of.
    @State private var frame: CGRect = .zero

    @Environment(\.colorScheme) private var scheme

    var body: some View {
        ZStack(alignment: .top) {
            // The theme's photo ground, the same one the grid tiles use.
            MB.color.photoWarmAlt

            TabView(selection: $page) {
                ForEach(Array(images.enumerated()), id: \.offset) { offset, url in
                    MBProductImage(url: url, cornerRadius: 0, background: MB.color.photoWarmAlt)
                        .tag(offset)
                }
            }
            .tabViewStyle(.page(indexDisplayMode: .never))
            .background {
                GeometryReader { geometry in
                    Color.clear
                        .onChange(of: geometry.frame(in: .global), initial: true) { _, value in
                            frame = value
                        }
                }
            }
            .contentShape(Rectangle())
            .onTapGesture { onOpen(page, frame) }

            if let badge {
                MBStatusPill(badge, background: MB.color.scrim, contentColor: MB.color.onScrim)
                    .padding(.leading, 16)
                    .padding(.top, ProductHero.chromeHeight + 8)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .opacity(1 - closed)
            }

            if images.count > 1 {
                // On a pill of their own: the dots sit on the photograph, and
                // drawn in the theme's ink they went missing on every picture
                // that happened to be the same tone.
                HStack(spacing: 5) {
                    ForEach(images.indices, id: \.self) { index in
                        Capsule()
                            .fill(index == page
                                  ? MB.color.onScrim
                                  : MB.color.onScrim.opacity(0.45))
                            .frame(width: index == page ? 18 : 6, height: 6)
                            .animation(MBMotion.easeQuick, value: page)
                    }
                }
                .padding(.horizontal, 9)
                .padding(.vertical, 7)
                .background(MB.color.scrim)
                .clipShape(Capsule())
                .frame(maxHeight: .infinity, alignment: .bottom)
                .padding(.bottom, 18)
                .opacity(1 - closed)
            }
        }
        // Applied to the whole frame, ground included, or the picture would
        // slide out of its own backdrop.
        .offset(y: lag)
        .frame(height: ProductHero.height)
        .clipped()
    }
}

/// The bar over the photo: three buttons, and a surface that arrives under them.
///
/// Nothing else. It used to collect the product's name and its price as the page
/// scrolled, which meant the top of the screen carried a second copy of both —
/// the panel below has them and the buy bar at the foot of the screen has the
/// number, so a third set sliding into a bar that already holds three controls
/// made the top of the page busiest exactly when the customer had scrolled past
/// the part that needed explaining.
struct ProductChromeView: View {
    let product: ProductDTO?
    /// How far the page has covered the photograph behind this bar, 0…1.
    let cover: CGFloat
    let onBack: () -> Void
    let onToggleFavorite: () -> Void
    let onShare: () -> Void

    @Environment(\.colorScheme) private var scheme

    var body: some View {
        HStack(spacing: 6) {
            GlassButton(glyph: "arrow-left", cover: cover, action: onBack)
            Spacer(minLength: 0)
            if let product {
                GlassButton(
                    glyph: "heart",
                    tint: product.isFavorite ? MB.color.danger : MB.color.ink,
                    cover: cover,
                    action: onToggleFavorite
                )
                GlassButton(glyph: "share", cover: cover, action: onShare)
            }
        }
        .frame(height: 44)
        .padding(.horizontal, 14)
        .padding(.vertical, 10)
        .padding(.top, ProductHero.statusBarInset)
        .background {
            ZStack {
                // A wash first, then the page's surface over it.
                //
                // The photograph runs to the top of the screen, so what is
                // behind the system's own clock and battery is whatever the
                // seller photographed. iOS picks the colour of that clock from
                // the appearance rather than from anything a SwiftUI view can
                // say, so the wash goes the way the appearance already went:
                // pale under dark text, dark under light text. Strongest at the
                // very edge and gone by the row of buttons, so it reads as the
                // picture lightening rather than as a band laid across it.
                LinearGradient(
                    stops: [
                        .init(color: washColor.opacity(0.62), location: 0),
                        .init(color: washColor.opacity(0.2), location: 0.55),
                        .init(color: washColor.opacity(0), location: 1),
                    ],
                    startPoint: .top,
                    endPoint: .bottom
                )
                MB.color.surface.opacity(ProductHero.barCover(cover))
            }
            .ignoresSafeArea(edges: .top)
        }
    }

    private var washColor: Color { scheme == .dark ? .black : .white }
}

/// A circular button legible on a photograph and on a plain surface alike: the
/// bar's own fill, which is a step off both.
///
/// Sized to be hit rather than to be tidy — 44 pt, which is what a thumb needs
/// and what these three controls sitting on a photograph deserve, since a miss
/// scrolls the page instead. The disc thins out as the bar grows its own
/// surface: three grey circles on a plain bar are three more shapes than the row
/// needs, so by then the glyphs are left standing on the bar as they are on
/// every other screen's header.
private struct GlassButton: View {
    let glyph: String
    var tint: Color = MB.color.ink
    var cover: CGFloat = 0
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            MBIcon(glyph, size: 21, tint: tint, lineWidth: 1.9)
                .frame(width: 44, height: 44)
                .background(MB.color.fill.opacity(1 - ProductHero.barCover(cover)))
                .clipShape(Circle())
                .contentShape(Circle())
        }
        .buttonStyle(MBCardPressStyle(pressedScale: 0.92))
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
                .padding(.vertical, 2)
            }
        }
        .padding(.top, 6)
    }
}
