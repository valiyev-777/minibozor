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

/// Screen 14 — Mahsulot.
///
/// The photograph is the first thing the screen is about, so it runs the full
/// width under the status bar and the page reads photo, name, description. Its
/// motion answers the scroll: nothing here plays on its own.
struct ProductView: View {
    let productId: Int

    @Environment(Router.self) var router
    @Environment(CartRepository.self) var cart

    @State var model = ProductModel()
    @State var toast: String?

    /// How far the photo has closed away behind the page, 0…1.
    @State private var closed: CGFloat = 0
    /// Where the name on the page currently ends, in screen coordinates.
    @State private var nameBottom: CGFloat = .greatestFiniteMagnitude

    /// How far the name has been handed from the page to the bar, 0…1.
    ///
    /// Measured against the name itself rather than the card holding it:
    /// keying it to the card's top edge hands the name over while it is still
    /// in plain sight a padding's distance below the bar.
    private var handover: CGFloat {
        let barBottom = ProductHero.chromeHeight
        return min(max((barBottom - nameBottom) / 20, 0), 1)
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
                handover: handover,
                onBack: { router.pop() },
                onToggleFavorite: { Task { await model.toggleFavorite() } },
                onShare: { share(model.product) }
            )
        }
        .ignoresSafeArea(edges: .top)
        .navigationBarBackButtonHidden()
        .mbToast($toast)
        .safeAreaInset(edge: .bottom) { buyBar }
        .task { await model.load(id: productId) }
    }

    /// Always there. The price inside it stands down once the bar at the top
    /// has taken it over, and the button widens into the room that leaves —
    /// but the way to buy the thing never leaves the screen.
    @ViewBuilder
    private var buyBar: some View {
        if let product = model.product {
            MBBottomBar {
                HStack(spacing: 14) {
                    if handover < 0.6 {
                        MBPriceRow(
                            price: product.price,
                            oldPrice: product.oldPrice,
                            discountPercent: product.discountPercent,
                            style: MB.type.title3
                        )
                        .transition(.opacity)
                    }
                    MBPrimaryButton(
                        product.inStock ? L("savatga") : L("mavjud_emas"),
                        enabled: product.inStock,
                        loading: model.adding
                    ) {
                        Task { toast = await model.addToCart(using: cart) }
                    }
                }
                .animation(.easeInOut(duration: 0.2), value: handover < 0.6)
            }
        }
    }

    private func content(_ product: ProductDTO) -> some View {
        ScrollView {
            LazyVStack(spacing: 12) {
                ProductHeroView(images: product.images, badge: product.badge, closed: closed)
                    .background {
                        GeometryReader { geometry in
                            Color.clear.onChange(of: geometry.frame(in: .global).minY,
                                                 initial: true) { _, minY in
                                let travel = ProductHero.height * 0.55
                                closed = min(max(-minY / travel, 0), 1)
                            }
                        }
                    }

                // Grouped by what a section is for rather than one card each:
                // "what is this", "which one", "the small print". Five floating
                // panels read as clutter; one panel for the lot would be a long
                // box with no seams where the subject changes.
                identity(product)
                options(product)
                smallPrint(product)
                reviews(product)

                if !model.similar.isEmpty {
                    MBCard(padding: 0, cornerRadius: 0) {
                        RecommendationsRail(products: model.similar) { id in
                            router.push(.product(id: id))
                        }
                        Spacer().frame(height: 16)
                    }
                }

                Spacer().frame(height: 24)
            }
        }
        .coordinateSpace(name: ProductHero.space)
    }

    private func identity(_ product: ProductDTO) -> some View {
        MBCard(cornerRadius: 0) {
            // No price here: it is in the buy bar a thumb's reach away and in
            // the bar once the photo closes, so a third copy is just noise.
            Text(product.title)
                .mbFont(MB.type.title2)
                .foregroundStyle(MB.color.ink)
                .background {
                    GeometryReader { geometry in
                        Color.clear.onChange(of: geometry.frame(in: .global).maxY,
                                             initial: true) { _, maxY in
                            nameBottom = maxY
                        }
                    }
                }
            if !product.subtitle.isEmpty {
                Spacer().frame(height: 4)
                Text(product.subtitle)
                    .mbFont(MB.type.bodySmall)
                    .foregroundStyle(MB.color.textTertiary)
            }
            Spacer().frame(height: 10)
            HStack(spacing: 12) {
                MBRating(rating: product.rating, reviewsCount: product.reviewsCount)
                if product.isOriginal {
                    MBStatusPill(
                        L("original"),
                        background: MB.color.successBg,
                        contentColor: MB.color.success
                    )
                }
            }
            if !product.description.isEmpty {
                Spacer().frame(height: 14)
                MBDivider()
                Spacer().frame(height: 14)
                SectionHeader(title: L("tavsif"))
                Spacer().frame(height: 10)
                MBCollapsibleText(text: product.description)
            }
        }
    }

    @ViewBuilder
    private func options(_ product: ProductDTO) -> some View {
        if !product.sizes.isEmpty || !product.colors.isEmpty {
            MBCard(cornerRadius: 0) {
                if !product.sizes.isEmpty {
                    SectionHeader(title: L("olcham"), subtitle: L("olchamlar_jadvali"))
                    Spacer().frame(height: 12)
                    FlowLayout(spacing: 8) {
                        ForEach(product.sizes) { variant in
                            MBSizeChip(
                                variant.label,
                                selected: variant.id == model.selectedSizeId,
                                enabled: variant.inStock
                            ) {
                                model.selectedSizeId = variant.id
                            }
                        }
                    }
                }
                if !product.sizes.isEmpty && !product.colors.isEmpty {
                    Spacer().frame(height: 14)
                    MBDivider()
                    Spacer().frame(height: 14)
                }
                if !product.colors.isEmpty {
                    SectionHeader(title: L("rang"))
                    Spacer().frame(height: 12)
                    HStack(spacing: 10) {
                        ForEach(product.colors) { variant in
                            ColorSwatch(
                                hex: variant.value,
                                label: variant.label,
                                selected: variant.id == model.selectedColorId
                            ) {
                                model.selectedColorId = variant.id
                            }
                        }
                    }
                }
            }
        }
    }

    private func smallPrint(_ product: ProductDTO) -> some View {
        MBCard(cornerRadius: 0) {
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
                    subtitle: L("sotuvchi_va_qoldiq", product.seller, product.stockLeft)
                )
            }
            if !product.specs.isEmpty {
                Spacer().frame(height: 14)
                MBDivider()
                Spacer().frame(height: 14)
                MBExpandableSection(
                    L("xususiyatlari"),
                    subtitle: LPlural("n_items", count: product.specs.count,
                                      "\(product.specs.count)")
                ) {
                    ForEach(product.specs, id: \.key) { spec in
                        MBKeyValueRow(key: spec.key, value: spec.value)
                    }
                }
            }
        }
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

private struct ColorSwatch: View {
    let hex: String
    let label: String
    let selected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            VStack(spacing: 6) {
                Circle()
                    .fill(Color(hexString: hex, fallback: MB.color.fill))
                    .frame(width: selected ? 34 : 38, height: selected ? 34 : 38)
                    .padding(selected ? 3 : 1)
                    .background(selected ? MB.color.ink : MB.color.border)
                    .clipShape(Circle())
                Text(label).mbFont(MB.type.micro).foregroundStyle(MB.color.textSecondary)
            }
        }
        .buttonStyle(.plain)
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
