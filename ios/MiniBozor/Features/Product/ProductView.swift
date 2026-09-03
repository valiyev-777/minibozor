import SwiftUI
import Observation

@Observable
final class ProductModel {
    var loading = true
    var errorMessage: String?
    var product: ProductDTO?
    var summary: ReviewSummaryDTO?
    var topReviews: [ReviewDTO] = []
    var similar: [ProductCardDTO] = []
    var selectedSizeId: Int?
    var selectedColorId: Int?
    var adding = false

    private let catalog = CatalogRepository()

    @MainActor
    func load(id: Int) async {
        loading = true
        errorMessage = nil

        switch await catalog.product(id) {
        case .success(let value):
            product = value
            // Preselect the first in-stock size, as the design shows.
            selectedSizeId = value.sizes.first(where: \.inStock)?.id
            selectedColorId = value.colors.first?.id
        case .failure(let message):
            errorMessage = message
        }
        loading = false

        if case .success(let value) = await catalog.reviewSummary(productId: id) { summary = value }
        if case .success(let page) = await catalog.reviews(productId: id, stars: nil, page: 1) {
            topReviews = Array(page.items.prefix(2))
        }
        if case .success(let items) = await catalog.similar(to: id) { similar = items }
    }

    @MainActor
    func toggleFavorite() async {
        guard let product else { return }
        _ = await catalog.setFavorite(productId: product.id, favorite: !product.isFavorite)
        self.product?.isFavorite.toggle()
    }

    @MainActor
    func addToCart(using cart: CartRepository) async -> String {
        guard let product else { return "" }
        adding = true
        // Both, not one of the two: a cart line carries a size *and* a colour,
        // and sending only the size made the same shirt land as a second line
        // with its colour lost.
        let outcome = await cart.add(
            productId: product.id,
            variantId: selectedSizeId,
            colorVariantId: selectedColorId
        )
        adding = false
        return outcome.errorMessage ?? L("savatga_qoshildi")
    }
}

/// Which block of the page is which, for the staggered entrance.
///
/// The blocks enter staggered against these numbers and leave against them
/// reversed, so the page builds from the photograph down and comes apart from
/// the bottom up. Named rather than counted at the call sites: a block that is
/// only there for some products (the options, the description) would otherwise
/// shift every number under it, and the stagger would change with the product.
private enum Block {
    static let hero = 0
    static let identity = 1
    static let options = 2
    static let description = 3
    static let smallPrint = 4
    static let reviews = 5
    static let similar = 6
}

/// Screen 14 — Mahsulot.
///
/// The photograph is the first thing the screen is about, so it runs the full
/// width to the very top of the screen and the page climbs over it as it
/// scrolls. Its motion answers the scroll; the only thing that plays on its own
/// is the page's own arrival and departure.
struct ProductView: View {
    let productId: Int

    @Environment(Router.self) var router
    @Environment(CartRepository.self) var cart
    @Environment(TabSelection.self) var tabSelection

    @State var model = ProductModel()
    @State var toast: String?

    /// How far the page has covered the photograph, 0…1.
    @State private var closed: CGFloat = 0
    /// Points the photograph hangs back from the scroll.
    @State private var lag: CGFloat = 0
    /// Where the panel below the photograph starts, in screen coordinates.
    @State private var panelTop: CGFloat = .greatestFiniteMagnitude
    /// The photograph the full-screen view is showing, and where it grew from.
    @State private var viewer: ViewerTarget?
    /// True once the page has been asked to leave.
    @State private var leaving = false

    /// The photograph a tap opened, and the frame it was sitting in.
    private struct ViewerTarget: Identifiable {
        let page: Int
        let origin: CGRect
        var id: Int { page }
    }

    /// How far the page has crossed under the bar, 0…1.
    ///
    /// The panel below the photograph is drawn over it, so the moment its top
    /// edge passes the bar's bottom edge is the moment what is behind the bar
    /// stops being a photograph. That is when the bar grows its own surface —
    /// one number for the lot, so nothing can disagree about when it happens.
    private var cover: CGFloat {
        min(max((ProductHero.chromeHeight - panelTop) / 20, 0), 1)
    }

    var body: some View {
        ZStack(alignment: .top) {
            MB.color.canvas.ignoresSafeArea()

            if model.loading {
                ProductSkeleton()
            } else if let error = model.errorMessage {
                MBErrorState(message: error) { Task { await model.load(id: productId) } }
                    .padding(.top, ProductHero.chromeHeight)
            } else if let product = model.product {
                content(product)
            }

            ProductChromeView(
                product: model.product,
                cover: cover,
                onBack: leave,
                onToggleFavorite: { Task { await model.toggleFavorite() } },
                onShare: { share(model.product) }
            )
            .opacity(leaving ? 0 : 1)
            .animation(MBMotion.leave, value: leaving)
        }
        .ignoresSafeArea(edges: .top)
        .navigationBarBackButtonHidden()
        .mbToast($toast)
        .safeAreaInset(edge: .bottom) { buyBar }
        // Over everything, the buy bar included: while it is open the
        // photograph is the screen. An overlay rather than a cover sheet, so the
        // picture grows out of the frame that was tapped instead of sliding up
        // from the bottom of the screen.
        .overlay {
            if let viewer, let product = model.product {
                HeroViewerView(
                    images: product.images,
                    initialPage: viewer.page,
                    origin: viewer.origin
                ) {
                    self.viewer = nil
                }
            }
        }
        .task { await model.load(id: productId) }
    }

    /// Leaves the way the page arrived: the blocks sink back, the bars go, and
    /// only then does the navigation happen.
    private func leave() {
        guard !leaving else { return }
        leaving = true
        Task {
            try? await Task.sleep(for: .seconds(MBMotion.pageExit))
            router.pop()
        }
    }

    /// This product's line in the cart, if it is already in there.
    private var cartLine: CartItemDTO? {
        guard let product = model.product else { return nil }
        return cart.cart?.items.first { $0.productId == product.id }
    }

    /// The way to buy the thing, what it costs, and when it arrives.
    ///
    /// The price sits beside the button and stays there: this is the bar the
    /// thumb is already on, and a customer who has scrolled to the reviews
    /// should not have to go back up to check the number they are about to agree
    /// to. It used to stand down halfway through the scroll, which is exactly
    /// when it was most wanted. The panel at the top of the page keeps its own
    /// copy, so the number is on screen wherever the page has got to.
    ///
    /// Once the product is in the cart the button gives way to a quantity
    /// stepper and a way through to the cart, so hammering the same spot adjusts
    /// a count instead of piling duplicate lines into it.
    @ViewBuilder
    private var buyBar: some View {
        if let product = model.product, !leaving {
            MBBottomBar {
                HStack(spacing: 12) {
                    if let line = cartLine {
                        // Where the shelf ends. The bar could otherwise walk
                        // the count up to ninety-nine of something there were
                        // three of.
                        MBQuantityStepper(
                            quantity: line.quantity,
                            minimum: 0,
                            maximum: Swift.max(product.stockLeft, 1),
                            size: 44
                        ) { quantity in
                            Task { await cart.setQuantity(itemId: line.id, quantity: quantity) }
                        }
                        MBPrimaryButton(L("otish"), leadingGlyph: "cart") {
                            tabSelection.select("cart")
                        }
                    } else {
                        // Wraps rather than takes a share of the row: the button
                        // is the thing being aimed at, so it gets everything the
                        // number does not need.
                        VStack(alignment: .leading, spacing: 2) {
                            MBPriceRow(
                                price: product.price,
                                oldPrice: product.oldPrice,
                                style: MB.type.title3,
                                reservesFootnote: false
                            )
                            // Under the price, where the decision is being
                            // made. It had been a clause in the seller's row
                            // further up the page — "Sotuvchi · 25 dona qoldi" —
                            // which is the one place nobody reads twice.
                            StockLine(stockLeft: product.stockLeft)
                        }
                        .fixedSize(horizontal: true, vertical: false)
                        MBPrimaryButton(
                            product.inStock ? L("savatga") : L("mavjud_emas"),
                            enabled: product.inStock,
                            loading: model.adding
                        ) {
                            Task { toast = await model.addToCart(using: cart) }
                        }
                    }
                }
                .animation(MBMotion.ease, value: cartLine?.quantity)
            }
            .transition(.move(edge: .bottom).combined(with: .opacity))
        }
    }

    private func content(_ product: ProductDTO) -> some View {
        ScrollView {
            // No blanket spacing: the first panel has to butt straight up
            // against the photograph, or the gap shows as a strip of bare page
            // in front of it. Every panel after it carries its own gap.
            LazyVStack(spacing: 0) {
                ProductHeroView(
                    images: product.images,
                    badge: product.badge,
                    closed: closed,
                    lag: lag,
                    onOpen: { page, frame in
                        viewer = ViewerTarget(page: page, origin: frame)
                    }
                )
                .background {
                    GeometryReader { geometry in
                        Color.clear.onChange(of: geometry.frame(in: .global).minY,
                                             initial: true) { _, minY in
                            let travel = ProductHero.height * 0.55
                            closed = min(max(-minY / travel, 0), 1)
                            // Holds back at a fraction of the scroll, so the
                            // page's own panels are seen crossing in front of
                            // the picture rather than arriving once it has gone.
                            lag = max(-minY, 0) * 0.7
                        }
                    }
                }
                // Fades only, and stays put: it runs under the status bar, and a
                // photograph rising into place there leaves a strip of bare page
                // above it the whole way up.
                .mbReveal(Block.hero, leaving: leaving, rise: 0)

                // The order the page is read in: what it is and what it costs,
                // what buyers made of it, which one to buy, the seller's own
                // description, the small print, and the reviews in full.
                identity(product)
                    // Above the photo, and overlapping it because the photo
                    // hangs back — so the panel is seen crossing in front of the
                    // picture rather than arriving once it has gone.
                    .zIndex(1)
                    .mbReveal(Block.identity, leaving: leaving)

                options(product)
                    .mbReveal(Block.options, leaving: leaving)

                description(product)
                    .mbReveal(Block.description, leaving: leaving)

                smallPrint(product)
                    .mbReveal(Block.smallPrint, leaving: leaving)

                reviews(product)
                    .mbReveal(Block.reviews, leaving: leaving)

                if !model.similar.isEmpty {
                    MBCard(padding: 0, cornerRadius: 0) {
                        RecommendationsRail(products: model.similar) { id in
                            router.push(.product(id: id))
                        }
                        Spacer().frame(height: 16)
                    }
                    .padding(.top, 12)
                    .mbReveal(Block.similar, leaving: leaving)
                }

                Spacer().frame(height: 24)
            }
        }
        .coordinateSpace(name: ProductHero.space)
        .scrollIndicators(.hidden)
    }

    /// The name, the number, and what buyers made of it.
    ///
    /// Name first, then the price. The name is what the page is about and the
    /// price is the fact being weighed about it, so the name leads at the
    /// panel's heaviest size and the price answers it a step below, set larger
    /// still but on its own line with the saving beside it. Read in that order
    /// it is a sentence; the other way round it was a number looking for a
    /// subject. The panel is measured from its own top, because the bar above
    /// grows its surface at the moment this edge passes under it.
    private func identity(_ product: ProductDTO) -> some View {
        MBCard(cornerRadius: 0) {
            Text(product.title)
                .mbFont(MB.type.title1)
                .foregroundStyle(MB.color.ink)
            if !product.subtitle.isEmpty {
                Spacer().frame(height: 5)
                Text(product.subtitle)
                    .mbFont(MB.type.bodySmall)
                    .foregroundStyle(MB.color.textTertiary)
            }
            Spacer().frame(height: 12)
            HStack(alignment: .center, spacing: 10) {
                Text(Format.sum(product.price))
                    .mbFont(MB.type.display)
                    .foregroundStyle(MB.color.ink)
                    .lineLimit(1)
                if let off = product.discountPercent {
                    MBDiscountPill(percent: off, large: true)
                }
                Spacer(minLength: 0)
            }
            if let was = product.oldPrice, was > product.price {
                Spacer().frame(height: 3)
                Text(Format.grouped(was))
                    .mbFont(MB.type.sectionHead)
                    .strikethrough()
                    .foregroundStyle(MB.color.textQuaternary)
            }
            // Where the description used to be. What a stranger's page owes a
            // buyer at this point is other buyers, not the seller's own prose.
            Spacer().frame(height: 16)
            RatingPanel(
                rating: model.summary?.rating ?? product.rating,
                reviewsCount: model.summary?.total ?? product.reviewsCount,
                soldCount: product.sold,
                photos: model.summary?.photoStrip ?? [],
                photosTotal: model.summary?.photoCount ?? 0
            ) {
                router.push(.reviews(productId: product.id))
            }
            if product.sold > 0 {
                Spacer().frame(height: 12)
                SoldLine(soldCount: product.sold)
            }
            if product.isOriginal {
                Spacer().frame(height: 12)
                MBStatusPill(
                    L("original"),
                    background: MB.color.successBg,
                    contentColor: MB.color.success
                )
            }
        }
        .background {
            GeometryReader { geometry in
                Color.clear.onChange(of: geometry.frame(in: .global).minY,
                                     initial: true) { _, minY in
                    panelTop = minY
                }
            }
        }
    }

    /// The seller's own description, straight after the choice and above the
    /// small print.
    ///
    /// A description is what someone reads once they have decided to care — a
    /// page of prose between the name and the "which one" is a page nobody
    /// scrolls past, and buried under the specifications it is a page nobody
    /// finds. Folded down to its opening lines, with the rest behind "Batafsil".
    @ViewBuilder
    private func description(_ product: ProductDTO) -> some View {
        if !product.description.isEmpty {
            MBCard(cornerRadius: 0) {
                SectionHeader(title: L("tavsif"))
                Spacer().frame(height: 12)
                // Headings, lists and the shop's own photographs, not one flat
                // paragraph: a seller writing about a pair of shoes writes a
                // page, and the mark-up they send used to be printed raw.
                MBRichText(text: product.description)
            }
            .padding(.top, 12)
        }
    }

    /// Colour first, then size: the colour is what the photograph above is
    /// showing, and changing it changes what a size is being chosen for.
    @ViewBuilder
    private func options(_ product: ProductDTO) -> some View {
        if !product.sizes.isEmpty || !product.colors.isEmpty {
            MBCard(cornerRadius: 0) {
                if !product.colors.isEmpty {
                    ColorOptionsRow(
                        colors: product.colors,
                        selectedId: model.selectedColorId,
                        productImages: product.images
                    ) { id in
                        model.selectedColorId = id
                    }
                }
                if !product.sizes.isEmpty && !product.colors.isEmpty {
                    Spacer().frame(height: 16)
                    MBDivider()
                    Spacer().frame(height: 16)
                }
                if !product.sizes.isEmpty {
                    SizeOptionsRow(
                        sizes: product.sizes,
                        selectedId: model.selectedSizeId
                    ) { id in
                        model.selectedSizeId = id
                    }
                }
            }
            .padding(.top, 12)
        }
    }

    /// The small print, folded: the numbers first, then the terms.
    private func smallPrint(_ product: ProductDTO) -> some View {
        MBCard(cornerRadius: 0) {
            if !product.specs.isEmpty {
                MBExpandableSection(
                    L("xususiyatlari"),
                    subtitle: LPlural("n_items", count: product.specs.count,
                                      "\(product.specs.count)")
                ) {
                    ForEach(product.specs, id: \.key) { spec in
                        MBKeyValueRow(key: spec.key, value: spec.value)
                    }
                }
                Spacer().frame(height: 14)
                MBDivider()
                Spacer().frame(height: 14)
            }
            // Folded, but the delivery line rides on the header: it is the one
            // fact here that helps someone decide, and hiding it to tidy the
            // page would be a poor trade.
            MBExpandableSection(L("yetkazish_va_kafolat"), subtitle: product.deliveryNote) {
                InfoRow(glyph: "box", title: L("yetkazish"), subtitle: product.deliveryNote)
                MBDivider()
                InfoRow(
                    glyph: "ret",
                    title: L("qaytarish"),
                    subtitle: L("qaytarish_14_kun_ichida_qadoq_butun_bolsa")
                )
                if let warranty = product.warranty {
                    MBDivider()
                    InfoRow(glyph: "gear", title: L("kafolat"), subtitle: warranty)
                }
                MBDivider()
                InfoRow(
                    glyph: "basket",
                    title: L("sotuvchi"),
                    // The seller, and only the seller. What is left moved to the
                    // buy bar, where the count is a reason rather than a clause
                    // in a row about delivery.
                    subtitle: product.seller
                )
            }
        }
        .padding(.top, 12)
    }

    private func reviews(_ product: ProductDTO) -> some View {
        MBCard(cornerRadius: 0) {
            SectionHeader(
                title: L("sharhlar"),
                subtitle: model.summary.map { LPlural("n_items", count: $0.total, "\($0.total)") },
                actionLabel: L("barchasi")
            ) {
                router.push(.reviews(productId: product.id))
            }
            Spacer().frame(height: 12)
            if model.topReviews.isEmpty {
                Text(L("hali_sharh_yoq_birinchi_boling"))
                    .mbFont(MB.type.bodySmall)
                    .foregroundStyle(MB.color.icon)
            } else {
                ForEach(model.topReviews) { review in
                    ReviewRow(review: review, onLike: nil)
                    Spacer().frame(height: 12)
                }
            }
        }
        .padding(.top, 12)
    }

    /// Hands the product to the system share sheet. The chooser is the
    /// customer's — nothing leaves the phone until they pick a destination.
    private func share(_ product: ProductDTO?) {
        guard let product else { return }
        let text = "\(product.title)\nminibozor://product/\(product.id)"
        let sheet = UIActivityViewController(activityItems: [text], applicationActivities: nil)
        UIApplication.shared.connectedScenes
            .compactMap { ($0 as? UIWindowScene)?.keyWindow?.rootViewController }
            .first?
            .present(sheet, animated: true)
    }
}

private struct InfoRow: View {
    let glyph: String
    let title: String
    let subtitle: String

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            MBIcon(glyph, size: 18, tint: MB.color.accent)
            VStack(alignment: .leading, spacing: 2) {
                Text(title).mbFont(MB.type.bodyBold).foregroundStyle(MB.color.ink)
                Text(subtitle).mbFont(MB.type.meta).foregroundStyle(MB.color.icon)
            }
            Spacer(minLength: 0)
        }
        .padding(.vertical, 12)
    }
}
