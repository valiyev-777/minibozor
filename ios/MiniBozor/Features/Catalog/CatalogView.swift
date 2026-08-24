import SwiftUI
import Observation

@Observable
final class CatalogModel {
    var state: LoadState<[CategoryDTO]> = .loading
    private let catalog = CatalogRepository()

    @MainActor
    func load() async {
        switch await catalog.rootCategories() {
        case .success(let items): state = .ready(items)
        case .failure(let message): state = .failed(message)
        }
    }
}

/// Screen 10 — Katalog.
struct CatalogView: View {
    @Environment(Router.self) var router
    @State var model = CatalogModel()

    var body: some View {
        MBScreen {
            VStack(spacing: 0) {
                VStack(alignment: .leading, spacing: 12) {
                    Text("Katalog").mbFont(MB.type.title1).foregroundStyle(MB.color.ink)
                    MBSearchPill(placeholder: "Turkum yoki mahsulot qidirish") {
                        router.push(.search)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.horizontal, 20)
                .padding(.vertical, 12)
                .background(MB.color.surface)

                LoadStateView(state: model.state, onRetry: { Task { await model.load() } }) { categories in
                    ScrollView {
                        MBCard(padding: 4) {
                            ForEach(Array(categories.enumerated()), id: \.element.id) { offset, category in
                                MBListRow(
                                    category.name,
                                    glyph: category.icon,
                                    subtitle: category.subtitle.isEmpty ? nil : category.subtitle,
                                    meta: category.productCount > 0
                                        ? "\(Format.grouped(category.productCount)) tovar" : nil
                                ) {
                                    if category.hasChildren {
                                        router.push(.subcategory(slug: category.slug))
                                    } else {
                                        router.push(
                                            .listing(category: category.slug, query: nil, title: category.name)
                                        )
                                    }
                                }
                                .padding(.horizontal, 12)
                                if offset != categories.count - 1 { MBDivider(inset: 62) }
                            }
                        }
                        .padding(12)
                        Spacer().frame(height: MB.metric.tabBarHeight + 26)
                    }
                }
            }
        }
        .task { await model.load() }
    }
}

@Observable
final class SubcategoryModel {
    var state: LoadState<(CategoryDTO, [CategoryDTO])> = .loading
    private let catalog = CatalogRepository()

    @MainActor
    func load(slug: String) async {
        async let parent = catalog.category(slug)
        async let children = catalog.children(of: slug)

        switch (await parent, await children) {
        case (.success(let category), .success(let items)):
            state = .ready((category, items))
        case (.failure(let message), _), (_, .failure(let message)):
            state = .failed(message)
        }
    }
}

/// Screen 11 — Subkategoriya.
struct SubcategoryView: View {
    let slug: String
    @Environment(Router.self) var router
    @State var model = SubcategoryModel()

    var body: some View {
        MBScreen {
            VStack(spacing: 0) {
                MBTopBar(model.state.value?.0.name ?? "Turkum", onBack: { router.pop() })

                LoadStateView(state: model.state, onRetry: { Task { await model.load(slug: slug) } }) { pair in
                    let (parent, children) = pair
                    ScrollView {
                        VStack(spacing: 12) {
                            MBCard(padding: 8) {
                                MBListRow(
                                    "Barcha tovarlar",
                                    glyph: parent.icon,
                                    meta: "\(Format.grouped(parent.productCount)) tovar"
                                ) {
                                    router.push(
                                        .listing(category: parent.slug, query: nil, title: parent.name)
                                    )
                                }
                                .padding(.horizontal, 8)
                            }

                            ForEach(children) { child in
                                MBCard(padding: 10) {
                                    Button {
                                        router.push(
                                            .listing(category: child.slug, query: nil, title: child.name)
                                        )
                                    } label: {
                                        HStack(spacing: 14) {
                                            MBProductImage(url: child.imageUrl, cornerRadius: MB.metric.radiusL)
                                                .frame(width: 60, height: 60)
                                            VStack(alignment: .leading, spacing: 3) {
                                                Text(child.name).mbFont(MB.type.bodyBold)
                                                    .foregroundStyle(MB.color.ink)
                                                Text("\(Format.grouped(child.productCount)) tovar")
                                                    .mbFont(MB.type.meta)
                                                    .foregroundStyle(MB.color.icon)
                                            }
                                            Spacer()
                                            Text("›").mbFont(MB.type.title3)
                                                .foregroundStyle(MB.color.hairlineStrong)
                                        }
                                        .contentShape(Rectangle())
                                    }
                                    .buttonStyle(.plain)
                                }
                            }
                        }
                        .padding(12)
                    }
                }
            }
        }
        .navigationBarBackButtonHidden()
        .task { await model.load(slug: slug) }
    }
}
