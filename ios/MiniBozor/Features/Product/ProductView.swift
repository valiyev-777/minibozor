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
struct ProductView: View {
    let productId: Int

    @Environment(Router.self) var router
    @Environment(CartRepository.self) var cart

    @State var model = ProductModel()
    @State var toast: String?

    var body: some View {
        MBScreen {
            VStack(spacing: 0) {
                MBTopBar(
                    title: "",
                    onBack: { router.pop() }
                ) {
                    if let product = model.product {
                        Button {
                            Task { await model.toggleFavorite() }
                        } label: {
                            MBIcon(
                                "heart",
                                size: 20,
                                tint: product.isFavorite ? MB.color.danger : MB.color.ink,
                                lineWidth: 1.9
                            )
                        }
                        .buttonStyle(.plain)
                    }
                }

                if model.loading {
                    MBLoading()
                } else if let error = model.errorMessage {
                    MBErrorState(message: error) { Task { await model.load(id: productId) } }
                } else if let product = model.product {
                    detail(product)
                }
            }
        }
        .navigationBarBackButtonHidden()
        .mbToast($toast)
        .safeAreaInset(edge: .bottom) {
            if let product = model.product {
                MBBottomBar {
                    HStack(spacing: 14) {
                        MBPriceRow(
                            price: product.price,
                            oldPrice: product.oldPrice,
                            discountPercent: product.discountPercent
                        )
                        MBPrimaryButton(
                            product.inStock ? L("savatga") : L("mavjud_emas"),
                            enabled: product.inStock,
                            loading: model.adding
                        ) {
                            Task { toast = await model.addToCart(using: cart) }
                        }
                        .frame(maxWidth: 190)
                    }
                }
            }
        }
        .task { await model.load(id: productId) }
    }

    private func detail(_ product: ProductDTO) -> some View {
        ScrollView {
            LazyVStack(spacing: 12) {
                Gallery(images: product.images, badge: product.badge)

                MBCard {
                    MBPriceRow(
                        price: product.price,
                        oldPrice: product.oldPrice,
                        discountPercent: product.discountPercent,
                        style: MB.type.display
                    )
                    Spacer().frame(height: 8)
                    Text(product.title).mbFont(MB.type.title3).foregroundStyle(MB.color.ink)
                    if !product.subtitle.isEmpty {
                        Spacer().frame(height: 4)
                        Text(product.subtitle).mbFont(MB.type.bodySmall)
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
                }
                .padding(.horizontal, 12)

                if !product.sizes.isEmpty {
                    MBCard {
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
                    .padding(.horizontal, 12)
                }

                if !product.colors.isEmpty {
                    MBCard {
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
                    .padding(.horizontal, 12)
                }

                MBCard {
                    InfoRow(glyph: "box", title: L("yetkazish"), subtitle: product.deliveryNote)
                    MBDivider()
                    InfoRow(glyph: "ret", title: L("qaytarish"), subtitle: L("qaytarish_14_kun_ichida_qadoq_butun_bolsa"))
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
                .padding(.horizontal, 12)

                if !product.description.isEmpty {
                    MBCard {
                        SectionHeader(title: L("tavsif"))
                        Spacer().frame(height: 10)
                        Text(product.description)
                            .mbFont(MB.type.bodySmall)
                            .foregroundStyle(MB.color.inkSoft)
                    }
                    .padding(.horizontal, 12)
                }

                if !product.specs.isEmpty {
                    MBCard {
                        SectionHeader(title: L("xususiyatlari"))
                        ForEach(product.specs, id: \.key) { spec in
                            MBKeyValueRow(key: spec.key, value: spec.value)
                        }
                    }
                    .padding(.horizontal, 12)
                }

                MBCard {
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
                .padding(.horizontal, 12)

                if !model.similar.isEmpty {
                    MBCard(padding: 0) {
                        SectionHeader(title: L("oxshash_tovarlar")).padding(16)
                        ScrollView(.horizontal, showsIndicators: false) {
                            HStack(alignment: .top, spacing: 10) {
                                ForEach(model.similar) { item in
                                    MBRailTile(product: item) {
                                        router.push(.product(id: item.id))
                                    }
                                }
                            }
                            .padding(.horizontal, 16)
                        }
                        .padding(.bottom, 16)
                    }
                    .padding(.horizontal, 12)
                }

                Spacer().frame(height: 20)
            }
        }
    }
}

private struct Gallery: View {
    let images: [String]
    let badge: String?
    @State var index = 0

    var body: some View {
        ZStack(alignment: .topLeading) {
            TabView(selection: $index) {
                ForEach(Array(images.enumerated()), id: \.offset) { offset, image in
                    MBProductImage(url: image, cornerRadius: 0, background: MB.color.photoWarm)
                        .tag(offset)
                }
            }
            .tabViewStyle(.page(indexDisplayMode: .never))
            .aspectRatio(1, contentMode: .fit)

            if let badge {
                MBStatusPill(badge, background: MB.color.ink.opacity(0.8), contentColor: .white)
                    .padding(14)
            }
        }
        .overlay(alignment: .bottom) {
            if images.count > 1 {
                HStack(spacing: 5) {
                    ForEach(0..<images.count, id: \.self) { position in
                        Capsule()
                            .fill(position == index ? MB.color.ink : MB.color.hairline)
                            .frame(width: position == index ? 18 : 6, height: 6)
                    }
                }
                .padding(.bottom, 14)
            }
        }
        .background(MB.color.surface)
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
