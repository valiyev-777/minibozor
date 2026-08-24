import SwiftUI
import Observation

@Observable
final class ListingModel {
    var query = ProductQuery()
    var items: [ProductCardDTO] = []
    var total = 0
    var page = 1
    var hasMore = false
    var loading = true
    var loadingMore = false
    var errorMessage: String?
    var filters: FiltersDTO?

    private let catalog = CatalogRepository()
    private var started = false

    @MainActor
    func start(category: String?, text: String?) async {
        guard !started else { return }
        started = true
        query.category = category
        query.text = text
        await reload()
        if case .success(let filters) = await catalog.filters(category: category) {
            self.filters = filters
        }
    }

    @MainActor
    func apply(_ newQuery: ProductQuery) async {
        query = newQuery
        await reload()
    }

    @MainActor
    func reload() async {
        loading = true
        errorMessage = nil
        switch await catalog.products(query, page: 1) {
        case .success(let payload):
            items = payload.items
            total = payload.total
            hasMore = payload.hasMore
            page = 1
        case .failure(let message):
            errorMessage = message
        }
        loading = false
    }

    @MainActor
    func loadMoreIfNeeded(current product: ProductCardDTO) async {
        guard hasMore, !loadingMore, !loading else { return }
        guard let index = items.firstIndex(where: { $0.id == product.id }),
              index >= items.count - 4 else { return }

        loadingMore = true
        if case .success(let payload) = await catalog.products(query, page: page + 1) {
            items.append(contentsOf: payload.items)
            page += 1
            hasMore = payload.hasMore
        }
        loadingMore = false
    }

    @MainActor
    func toggleFavorite(_ product: ProductCardDTO) async {
        _ = await catalog.setFavorite(productId: product.id, favorite: !product.isFavorite)
        if let index = items.firstIndex(where: { $0.id == product.id }) {
            items[index].isFavorite.toggle()
        }
    }
}

/// Screens 09 and 12 — the same grid, with or without a search term.
struct ListingView: View {
    let title: String
    let category: String?
    let query: String?

    @Environment(Router.self) var router
    @Environment(CartRepository.self) var cart

    @State var model = ListingModel()
    @State var showFilters = false
    @State var toast: String?

    var body: some View {
        MBScreen {
            VStack(spacing: 0) {
                MBTopBar(
                    title.isEmpty ? (query ?? "Tovarlar") : title,
                    subtitle: model.total > 0 ? "\(Format.grouped(model.total)) ta topildi" : nil,
                    onBack: { router.pop() }
                )
                toolbar
                content
            }
        }
        .navigationBarBackButtonHidden()
        .mbToast($toast)
        .task { await model.start(category: category, text: query) }
        .sheet(isPresented: $showFilters) {
            FiltersSheet(
                filters: model.filters,
                initial: model.query,
                resultCount: model.total
            ) { updated in
                showFilters = false
                Task { await model.apply(updated) }
            }
            .presentationDetents([.large])
            .presentationCornerRadius(MB.metric.radiusSheet)
        }
    }

    private var toolbar: some View {
        HStack(spacing: 8) {
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    ForEach(model.filters?.sorts ?? [], id: \.self) { option in
                        let key = option["key"] ?? ""
                        MBChip(option["label"] ?? "", selected: key == model.query.sort) {
                            var updated = model.query
                            updated.sort = key
                            Task { await model.apply(updated) }
                        }
                    }
                }
                .padding(.vertical, 2)
            }

            Button {
                showFilters = true
            } label: {
                let count = model.query.activeFilterCount
                HStack(spacing: 6) {
                    MBIcon("gear", size: 14, tint: count > 0 ? .white : MB.color.ink)
                    Text(count > 0 ? "Filtr · \(count)" : "Filtr")
                        .mbFont(MB.type.caption)
                        .foregroundStyle(count > 0 ? .white : MB.color.ink)
                }
                .padding(.horizontal, 14)
                .padding(.vertical, 9)
                .background(count > 0 ? MB.color.ink : MB.color.fill)
                .clipShape(Capsule())
            }
            .buttonStyle(.plain)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 10)
        .background(MB.color.surface)
    }

    @ViewBuilder
    private var content: some View {
        if model.loading && model.items.isEmpty {
            MBLoading()
        } else if let error = model.errorMessage, model.items.isEmpty {
            MBErrorState(message: error) { Task { await model.reload() } }
        } else if model.items.isEmpty {
            MBEmptyState(
                glyph: "search",
                title: "Hech narsa topilmadi",
                message: "Filtrlarni yumshatib yoki boshqa so'z bilan qidirib ko'ring.",
                actionLabel: model.query.activeFilterCount > 0 ? "Filtrlarni tozalash" : nil,
                onAction: { Task { await model.apply(model.query.cleared()) } }
            )
        } else {
            ScrollView {
                LazyVGrid(
                    columns: [GridItem(.flexible(), spacing: 16), GridItem(.flexible())],
                    spacing: 18
                ) {
                    ForEach(model.items) { product in
                        MBProductTile(
                            product: product,
                            onOpen: { router.push(.product(id: product.id)) },
                            onToggleFavorite: { Task { await model.toggleFavorite(product) } },
                            onAddToCart: {
                                Task {
                                    let outcome = await cart.add(productId: product.id, variantId: nil)
                                    toast = outcome.errorMessage ?? "Savatga qo'shildi"
                                }
                            }
                        )
                        .task { await model.loadMoreIfNeeded(current: product) }
                    }
                }
                .padding(14)
                if model.loadingMore {
                    ProgressView().tint(MB.color.accent).padding(.bottom, 20)
                }
            }
        }
    }
}
