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
    @Environment(TabSelection.self) private var tabSelection
    @State private var picking: ProductCardDTO?

    var body: some View {
        MBScreen {
            LoadStateView(state: model.state, onRetry: { Task { await model.load(city: session.city) } }) { home in
                ScrollView {
                    // Pinned, so the search stays while the feed runs under it.
                    // Searching is the one thing a customer may want at any
                    // depth of a page this long, and reaching it meant flinging
                    // back to the top; where they are delivering to is a thing
                    // they set once and read at the top, so that scrolls away.
                    LazyVStack(spacing: 12, pinnedViews: .sectionHeaders) {
                      // Outside the section, so it scrolls off and the search
                      // below it is what stays. Inside, it would be drawn under
                      // its own header.
                      cityRow
                      Section {
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
                      } header: {
                        searchRow
                      }
                    }
                }
            }
        }
        .mbToast($toast)
        .sheet(item: $picking) { card in
            VariantSheet(
                card: card,
                onDismiss: { picking = nil },
                onOpenCart: {
                    picking = nil
                    tabSelection.select("cart")
                }
            )
            .presentationDetents([.medium, .large])
            .presentationDragIndicator(.visible)
            .presentationCornerRadius(MB.metric.radiusSheet)
        }
        .task { await model.load(city: session.city) }
    }

    private var cityRow: some View {
        HStack(spacing: 7) {
            MBIcon("pin", size: 15, tint: MB.color.accent, lineWidth: 1.9)
            Text(session.city).mbFont(MB.type.bodyBold).foregroundStyle(MB.color.ink)
            Text("▾").mbFont(MB.type.micro).foregroundStyle(MB.color.hairlineStrong)
            Spacer()
        }
        .padding(.horizontal, 20)
        .padding(.top, 8)
        .padding(.bottom, 8)
        .frame(maxWidth: .infinity)
        .background(MB.color.surface)
    }

    /// The search pill, which stays at the top while the feed runs under it.
    ///
    /// Opaque, and the full width of the window: a pinned header is drawn over
    /// the list rather than beside it, so anything see-through here shows the
    /// products sliding along behind the placeholder. The shadow under it is
    /// what says the white above is in front of the white below — a drawn rule
    /// is found whether or not the eye was looking, and this page keeps no
    /// edges anywhere else.
    private var searchRow: some View {
        MBSearchPill(placeholder: L("mahsulot_va_turkumlar_qidirish")) {
            router.push(.search)
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 10)
        .frame(maxWidth: .infinity)
        .background(MB.color.surface)
        .overlay(alignment: .bottom) {
            LinearGradient(
                colors: [Color.black.opacity(0.085), .clear],
                startPoint: .top,
                endPoint: .bottom
            )
            .frame(height: 9)
            .offset(y: 9)
            .allowsHitTesting(false)
        }
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
            // No panel under a rail, unlike the grid and the deals pair. Those
            // two are bounded: everything they hold is on the screen at once,
            // and a surface drawn around them says where they stop. A rail does
            // not stop — it runs off the side of the screen, and a box around
            // something that leaves the box was the reason the third card read
            // as a card that would not fit rather than as one more card along.
            VStack(alignment: .leading, spacing: 12) {
                SectionHeader(
                    title: section.title,
                    subtitle: section.subtitle,
                    actionLabel: L("barchasi")
                ) {
                    router.push(
                        .listing(category: section.categorySlug, query: nil, title: section.title)
                    )
                }
                .padding(.horizontal, MB.metric.railEdge)

                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(alignment: .top, spacing: 10) {
                        ForEach(section.products) { product in
                            MBRailTile(product: product) { router.push(.product(id: product.id)) }
                        }
                    }
                    .padding(.horizontal, MB.metric.railEdge)
                }
            }
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
                // A product that comes in sizes or colours opens the picker
                // instead of being added with a variant we guessed. And
                // nothing else while one is on its way — see ListingView.
                guard picking == nil else { return }
                if product.hasVariants {
                    picking = product
                } else {
                    Task {
                        let outcome = await cart.add(productId: product.id)
                        toast = outcome.errorMessage ?? L("savatga_qoshildi")
                    }
                }
            }
        )
    }
}

/// How many times the banners repeat so the carousel can keep running forward.
private let BannerLoops = 101

private struct BannerCarousel: View {
    let banners: [BannerDTO]
    let onTap: (BannerDTO) -> Void

    /// Where the run starts, far enough in that nobody swipes off the front.
    @State var index = 0

    var body: some View {
        VStack(spacing: 10) {
            TabView(selection: $index) {
                ForEach(0..<(banners.count * BannerLoops), id: \.self) { page in
                    BannerCard(banner: banners[page % banners.count]) {
                        onTap(banners[page % banners.count])
                    }
                    .padding(.horizontal, 12)
                    .tag(page)
                }
            }
            .tabViewStyle(.page(indexDisplayMode: .never))
            .frame(height: MB.metric.bannerHeight)

            HStack(spacing: 4) {
                ForEach(0..<banners.count, id: \.self) { position in
                    let active = position == index % banners.count
                    Capsule()
                        .fill(active ? MB.color.accent : MB.color.hairlineStrong)
                        .frame(width: active ? 14 : 3.5, height: 3.5)
                        .animation(.easeInOut(duration: 0.26), value: index)
                }
            }
        }
        // Restarts on every settle, including after the customer swipes it
        // themselves, which is what stops it yanking the page out from under a
        // thumb rather than simply advancing on a timer.
        .onAppear {
            if index == 0 { index = banners.count * (BannerLoops / 2) }
        }
        .task(id: index) {
            guard banners.count > 1 else { return }
            // Back to the middle of the run when an end comes into view. The
            // jump is a whole number of banners, so the page it lands on is the
            // one already showing and nothing moves on screen.
            let middle = banners.count * (BannerLoops / 2)
            if abs(index - middle) > banners.count * (BannerLoops / 2 - 2) {
                var silent = Transaction()
                silent.disablesAnimations = true
                withTransaction(silent) { index = middle + index % banners.count }
                return
            }
            try? await Task.sleep(for: .seconds(4.5))
            guard !Task.isCancelled else { return }
            withAnimation(.easeInOut(duration: 0.7)) {
                    // Always the next page, never a modulo back to the first:
                // the run is long enough in both directions that forward is
                // always available, and the recentre below keeps it that way.
                index += 1
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
                            // A photograph where the shop supplied one, the
                            // line glyph where it did not — the grid holds both
                            // without looking mixed because the tile behind
                            // them is the same.
                            Group {
                                if let image = category.imageUrl,
                                   let parsed = AppConfig.media(image) {
                                    AsyncImage(url: parsed) { phase in
                                        if let picture = phase.image {
                                            picture.resizable().scaledToFit()
                                        } else {
                                            Color.clear
                                        }
                                    }
                                    .padding(MB.metric.categoryTile * 0.14)
                                } else {
                                    MBIcon(category.icon, size: 20)
                                }
                            }
                            .frame(width: MB.metric.categoryTile, height: MB.metric.categoryTile)
                            .background(MB.color.fill)
                            .clipShape(RoundedRectangle(cornerRadius: MB.metric.radiusXL,
                                                        style: .continuous))
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
