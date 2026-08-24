import SwiftUI
import Observation

@Observable
final class HomeModel {
    var state: LoadState<HomeDTO> = .loading

    private let catalog = CatalogRepository()

    @MainActor
    func load(city: String) async {
        if case .ready = state {} else { state = .loading }
        switch await catalog.home(city: city) {
        case .success(let home): state = .ready(home)
        case .failure(let message): state = .failed(message)
        }
    }

    @MainActor
    func toggleFavorite(_ product: ProductCardDTO, city: String) async {
        _ = await catalog.setFavorite(productId: product.id, favorite: !product.isFavorite)
        // The home payload carries `is_favorite`, so a quiet reload keeps every
        // tile in sync rather than just the one tapped.
        if case .success(let home) = await catalog.home(city: city) {
            state = .ready(home)
        }
    }
}

/// Screen 07 — Bosh sahifa. One request fills the whole page.
struct HomeView: View {
    @Environment(Router.self) var router
    @Environment(AppSession.self) var session
    @Environment(CartRepository.self) var cart

    @State var model = HomeModel()
    @State var toast: String?

    var body: some View {
        MBScreen {
            LoadStateView(state: model.state, onRetry: { Task { await model.load(city: session.city) } }) { home in
                ScrollView {
                    LazyVStack(spacing: 12) {
                        header
                        if !home.banners.isEmpty {
                            BannerCarousel(banners: home.banners) { banner in
                                router.push(.subcategory(slug: banner.targetValue))
                            }
                        }
                        CategoryGrid(categories: home.categories) { category in
                            router.push(.subcategory(slug: category.slug))
                        }
                        ForEach(home.sections) { section in
                            sectionView(section)
                        }
                        Spacer().frame(height: MB.metric.tabBarHeight + 26)
                    }
                }
            }
        }
        .mbToast($toast)
        .task { await model.load(city: session.city) }
    }

    private var header: some View {
        VStack(spacing: 10) {
            HStack(spacing: 7) {
                MBIcon("pin", size: 15, tint: MB.color.accent, lineWidth: 1.9)
                Text(session.city).mbFont(MB.type.bodyBold).foregroundStyle(MB.color.ink)
                Text("▾").mbFont(MB.type.micro).foregroundStyle(MB.color.hairlineStrong)
                Spacer()
            }
            MBSearchPill(placeholder: "Mahsulot va turkumlar qidirish") {
                router.push(.search)
            }
        }
        .padding(.horizontal, 20)
        .padding(.top, 8)
        .padding(.bottom, 14)
        .background(MB.color.surface)
    }

    @ViewBuilder
    private func sectionView(_ section: SectionDTO) -> some View {
        switch section.layout {
        case "deals":
            MBCard {
                SectionHeader(title: section.title, subtitle: section.subtitle)
                Spacer().frame(height: 12)
                HStack(alignment: .top, spacing: 10) {
                    ForEach(section.products) { product in
                        MBDealTile(product: product) { router.push(.product(id: product.id)) }
                    }
                }
            }
            .padding(.horizontal, 12)

        case "grid":
            MBCard(padding: 14) {
                SectionHeader(title: section.title, subtitle: section.subtitle)
                Spacer().frame(height: 14)
                LazyVGrid(
                    columns: [GridItem(.flexible(), spacing: 16), GridItem(.flexible())],
                    spacing: 18
                ) {
                    ForEach(section.products) { product in
                        tile(product)
                    }
                }
            }
            .padding(.horizontal, 12)

        default:
            MBCard(padding: 0) {
                SectionHeader(
                    title: section.title,
                    subtitle: section.subtitle,
                    actionLabel: "Barchasi"
                ) {
                    router.push(
                        .listing(category: section.categorySlug, query: nil, title: section.title)
                    )
                }
                .padding(16)

                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(alignment: .top, spacing: 10) {
                        ForEach(section.products) { product in
                            MBRailTile(product: product) { router.push(.product(id: product.id)) }
                        }
                    }
                    .padding(.horizontal, 16)
                }
                .padding(.bottom, 16)
            }
            .padding(.horizontal, 12)
        }
    }

    private func tile(_ product: ProductCardDTO) -> some View {
        MBProductTile(
            product: product,
            onOpen: { router.push(.product(id: product.id)) },
            onToggleFavorite: {
                Task { await model.toggleFavorite(product, city: session.city) }
            },
            onAddToCart: {
                Task {
                    let outcome = await cart.add(productId: product.id, variantId: nil)
                    toast = outcome.errorMessage ?? "Savatga qo'shildi"
                }
            }
        )
    }
}

private struct BannerCarousel: View {
    let banners: [BannerDTO]
    let onTap: (BannerDTO) -> Void

    @State var index = 0

    var body: some View {
        VStack(spacing: 10) {
            TabView(selection: $index) {
                ForEach(Array(banners.enumerated()), id: \.offset) { offset, banner in
                    BannerCard(banner: banner) { onTap(banner) }
                        .padding(.horizontal, 12)
                        .tag(offset)
                }
            }
            .tabViewStyle(.page(indexDisplayMode: .never))
            .frame(height: MB.metric.bannerHeight)

            HStack(spacing: 4) {
                ForEach(0..<banners.count, id: \.self) { position in
                    Capsule()
                        .fill(position == index ? MB.color.accent : MB.color.hairlineStrong)
                        .frame(width: position == index ? 14 : 3.5, height: 3.5)
                }
            }
        }
    }
}

private struct BannerCard: View {
    let banner: BannerDTO
    let onTap: () -> Void

    var body: some View {
        Button(action: onTap) {
            HStack(alignment: .top, spacing: 10) {
                VStack(alignment: .leading, spacing: 0) {
                    Text(banner.kicker)
                        .mbFont(MB.type.badge)
                        .foregroundStyle(.white.opacity(0.68))
                        .lineLimit(1)
                    Spacer(minLength: 0)
                    Text(banner.title)
                        .mbFont(MB.type.title1)
                        .foregroundStyle(.white)
                        .lineLimit(2)
                        .multilineTextAlignment(.leading)
                    Spacer().frame(height: 5)
                    Text(banner.subtitle)
                        .mbFont(MB.type.meta)
                        .foregroundStyle(.white.opacity(0.72))
                        .lineLimit(2)
                        .multilineTextAlignment(.leading)
                    Spacer().frame(height: 9)
                    Text(banner.cta)
                        .mbFont(MB.type.meta)
                        .fontWeight(.heavy)
                        .foregroundStyle(MB.color.heroFrom)
                        .padding(.horizontal, 13)
                        .padding(.vertical, 7)
                        .background(.white)
                        .clipShape(Capsule())
                }
                MBProductImage(url: banner.imageUrl, background: .white.opacity(0.08))
                    .frame(width: 110)
            }
            .padding(.leading, 18)
            .padding(.trailing, 14)
            .padding(.vertical, 15)
            .frame(height: MB.metric.bannerHeight)
            .background(
                LinearGradient(
                    colors: [
                        Color(hexString: banner.gradientFrom, fallback: MB.color.heroFrom),
                        Color(hexString: banner.gradientTo, fallback: MB.color.accent),
                    ],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                )
            )
            .clipShape(RoundedRectangle(cornerRadius: MB.metric.radiusXXL, style: .continuous))
        }
        .buttonStyle(.plain)
    }
}

private struct CategoryGrid: View {
    let categories: [CategoryDTO]
    let onTap: (CategoryDTO) -> Void

    var body: some View {
        MBCard(padding: 14) {
            LazyVGrid(
                columns: Array(repeating: GridItem(.flexible(), spacing: 4), count: 5),
                spacing: 14
            ) {
                ForEach(categories) { category in
                    Button {
                        onTap(category)
                    } label: {
                        VStack(spacing: 6) {
                            MBIcon(category.icon, size: 20)
                                .frame(width: MB.metric.categoryTile, height: MB.metric.categoryTile)
                                .background(MB.color.fill)
                                .clipShape(RoundedRectangle(cornerRadius: MB.metric.radiusXL, style: .continuous))
                            Text(category.name)
                                .mbFont(MB.type.micro)
                                .fontWeight(.semibold)
                                .foregroundStyle(MB.color.inkSoft)
                                .multilineTextAlignment(.center)
                                .lineLimit(2)
                                .frame(height: 24, alignment: .top)
                        }
                    }
                    .buttonStyle(.plain)
                }
            }
        }
        .padding(.horizontal, 12)
    }
}
