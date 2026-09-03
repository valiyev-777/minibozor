import SwiftUI
import Observation

@Observable
final class AddressesModel {
    var addresses: [AddressDTO] = []
    private let repo = OrderRepository()

    @MainActor
    func load() async {
        addresses = (await repo.addresses()).value ?? []
    }

    @MainActor
    func delete(_ id: Int) async {
        _ = await repo.deleteAddress(id: id)
        await load()
    }
}

/// Screen 33 — Manzillarim.
struct AddressesView: View {
    @Environment(Router.self) var router
    @State var model = AddressesModel()

    var body: some View {
        MBScreen {
            VStack(spacing: 0) {
                MBTopBar(L("manzillarim"), onBack: { router.pop() })
                ScrollView {
                    VStack(spacing: 12) {
                        ForEach(model.addresses) { address in
                            MBCard {
                                HStack(spacing: 12) {
                                    MBIcon(address.icon, size: 18)
                                        .frame(width: 38, height: 38)
                                        .background(MB.color.fill)
                                        .clipShape(RoundedRectangle(cornerRadius: MB.metric.radiusM, style: .continuous))
                                    Text(address.title).mbFont(MB.type.bodyBold)
                                        .foregroundStyle(MB.color.ink)
                                    if let badge = address.badge {
                                        MBStatusPill(
                                            badge,
                                            background: address.isDefault ? MB.color.accentTint : MB.color.fill,
                                            contentColor: address.isDefault ? MB.color.accent : MB.color.textSecondary
                                        )
                                    }
                                    Spacer()
                                    Button(L("ochirish")) { Task { await model.delete(address.id) } }
                                        .mbFont(MB.type.caption)
                                        .foregroundStyle(MB.color.danger)
                                }
                                Spacer().frame(height: 10)
                                Text(address.line).mbFont(MB.type.bodySmall)
                                    .foregroundStyle(MB.color.inkSoft)
                                if !address.meta.isEmpty {
                                    Text(address.meta).mbFont(MB.type.meta)
                                        .foregroundStyle(MB.color.icon)
                                }
                            }
                        }

                        MBCard(padding: 6) {
                            MBListRow(
                                L("yangi_manzil_qoshish"),
                                glyph: "pin",
                                tint: MB.color.accent
                            ) {
                                router.push(.addressForm)
                            }
                            .padding(.horizontal, 10)
                        }
                    }
                    .padding(12)
                }
            }
        }
        .navigationBarBackButtonHidden()
        .task { await model.load() }
    }
}

@Observable
final class MyReviewsModel {
    var reviews: [ReviewDTO] = []
    private let repo = ProfileRepository()

    @MainActor
    func load() async {
        reviews = (await repo.myReviews()).value?.items ?? []
    }

    @MainActor
    func delete(_ id: Int) async {
        _ = await repo.deleteReview(id: id)
        await load()
    }
}

/// Screen 34 — Sharhlarim.
struct MyReviewsView: View {
    @Environment(Router.self) var router
    @State var model = MyReviewsModel()

    var body: some View {
        MBScreen {
            VStack(spacing: 0) {
                MBTopBar(L("sharhlarim"), onBack: { router.pop() })
                if model.reviews.isEmpty {
                    MBEmptyState(
                        glyph: "star",
                        title: L("hali_sharh_yozmagansiz"),
                        message: L("yetkazilgan_tovarlarga_sharh_qoldiring")
                    )
                } else {
                    ScrollView {
                        VStack(spacing: 12) {
                            ForEach(model.reviews) { review in
                                MBCard {
                                    if let product = review.product {
                                        HStack {
                                            Text(product.title).mbFont(MB.type.caption)
                                                .foregroundStyle(MB.color.inkSoft)
                                                .lineLimit(1)
                                            Spacer()
                                            MBStatusPill(
                                                review.status == "published" ? L("e_lon_qilindi") : L("tekshirilmoqda"),
                                                background: review.status == "published"
                                                    ? MB.color.successBg : MB.color.warningBg,
                                                contentColor: review.status == "published"
                                                    ? MB.color.success : MB.color.warning
                                            )
                                        }
                                        .contentShape(Rectangle())
                                        .onTapGesture { router.push(.product(id: product.id)) }
                                        MBDivider().padding(.vertical, 12)
                                    }
                                    ReviewRow(review: review, onLike: nil)
                                    Spacer().frame(height: 10)
                                    Button(L("ochirish")) { Task { await model.delete(review.id) } }
                                        .mbFont(MB.type.caption)
                                        .foregroundStyle(MB.color.danger)
                                }
                            }
                        }
                        .padding(12)
                    }
                }
            }
        }
        .navigationBarBackButtonHidden()
        .task { await model.load() }
    }
}

@Observable
final class FavoritesModel {
    var items: [ProductCardDTO] = []
    var loading = true

    private let catalog = CatalogRepository()

    @MainActor
    func load() async {
        loading = true
        items = (await catalog.favorites()).value?.items ?? []
        loading = false
    }

    @MainActor
    func remove(_ id: Int) async {
        _ = await catalog.setFavorite(productId: id, favorite: false)
        items.removeAll { $0.id == id }
    }
}

/// Screen 35 — Sevimlilar.
struct FavoritesView: View {
    @Environment(Router.self) var router
    @Environment(CartRepository.self) var cart
    @Environment(TabSelection.self) private var tabSelection

    @State var model = FavoritesModel()
    @State var toast: String?
    @State private var picking: ProductCardDTO?

    var body: some View {
        MBScreen {
            VStack(spacing: 0) {
                MBTopBar(L("sevimlilar"), onBack: { router.pop() })
                if model.loading {
                    MBLoading()
                } else if model.items.isEmpty {
                    MBEmptyState(
                        glyph: "heart",
                        title: L("sevimlilar_bosh"),
                        message: L("yoqqan_tovarlarni_belgilab_qoying_narx"),
                        actionLabel: L("xaridni_boshlash"),
                        onAction: { router.popToRoot() }
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
                                    onToggleFavorite: { Task { await model.remove(product.id) } },
                                    // The sheet, as everywhere else. This was
                                    // the worst of the direct-add screens: a
                                    // favourite with sizes went into the basket
                                    // with no size chosen at all, because
                                    // nothing here ever opened a picker.
                                    onAddToCart: {
                                        if picking == nil { picking = product }
                                    }
                                )
                            }
                        }
                        .padding(14)
                    }
                }
            }
        }
        .navigationBarBackButtonHidden()
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
        .task { await model.load() }
    }
}
