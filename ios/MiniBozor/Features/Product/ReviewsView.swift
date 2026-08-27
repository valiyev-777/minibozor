import SwiftUI
import Observation

@Observable
final class ReviewsModel {
    var summary: ReviewSummaryDTO?
    var reviews: [ReviewDTO] = []
    var stars: Int?
    var loading = true

    private let catalog = CatalogRepository()
    private var productId = 0

    @MainActor
    func load(id: Int) async {
        productId = id
        if case .success(let value) = await catalog.reviewSummary(productId: id) { summary = value }
        await fetch()
    }

    @MainActor
    func filter(_ value: Int?) async {
        stars = value
        await fetch()
    }

    @MainActor
    func like(_ id: Int) async {
        if case .success(let updated) = await catalog.likeReview(id),
           let index = reviews.firstIndex(where: { $0.id == id }) {
            reviews[index] = updated
        }
    }

    @MainActor
    private func fetch() async {
        loading = true
        if case .success(let page) = await catalog.reviews(productId: productId, stars: stars, page: 1) {
            reviews = page.items
        }
        loading = false
    }
}

/// Screen 15 — Sharhlar.
struct ReviewsView: View {
    let productId: Int
    @Environment(Router.self) var router
    @State var model = ReviewsModel()

    var body: some View {
        MBScreen {
            VStack(spacing: 0) {
                MBTopBar(L("sharhlar"), onBack: { router.pop() })
                ScrollView {
                    VStack(spacing: 12) {
                        if let summary = model.summary { histogram(summary) }
                        filterChips
                        ForEach(model.reviews) { review in
                            MBCard {
                                ReviewRow(review: review) {
                                    Task { await model.like(review.id) }
                                }
                            }
                        }
                        if model.reviews.isEmpty && !model.loading {
                            MBCard {
                                Text(L("bu_filtr_boyicha_sharh_topilmadi"))
                                    .mbFont(MB.type.bodySmall)
                                    .foregroundStyle(MB.color.icon)
                            }
                        }
                    }
                    .padding(12)
                }
            }
        }
        .navigationBarBackButtonHidden()
        .safeAreaInset(edge: .bottom) {
            MBBottomBar {
                MBPrimaryButton(L("sharh_yozish"), leadingGlyph: "star") {
                    router.push(.writeReview(productId: productId, orderItemId: nil))
                }
            }
        }
        .task { await model.load(id: productId) }
    }

    private func histogram(_ summary: ReviewSummaryDTO) -> some View {
        MBCard {
            HStack(alignment: .center, spacing: 20) {
                VStack(spacing: 4) {
                    Text(Format.rating(summary.rating))
                        .mbFont(MB.type.display)
                        .foregroundStyle(MB.color.ink)
                    MBStars(rating: Int(summary.rating.rounded()))
                    Text(LPlural("n_reviews", count: summary.total, "\(summary.total)"))
                        .mbFont(MB.type.meta)
                        .foregroundStyle(MB.color.icon)
                }
                VStack(spacing: 6) {
                    ForEach(summary.distribution) { bucket in
                        HStack(spacing: 8) {
                            Text("\(bucket.stars)").mbFont(MB.type.micro)
                                .foregroundStyle(MB.color.textSecondary)
                            GeometryReader { proxy in
                                ZStack(alignment: .leading) {
                                    Capsule().fill(MB.color.fill)
                                    Capsule().fill(MB.color.star)
                                        .frame(width: proxy.size.width * CGFloat(bucket.percent) / 100)
                                }
                            }
                            .frame(height: 5)
                            Text("\(bucket.count)").mbFont(MB.type.micro)
                                .foregroundStyle(MB.color.icon)
                                .frame(width: 26, alignment: .trailing)
                        }
                    }
                }
            }
        }
    }

    private var filterChips: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                MBChip(L("hammasi"), selected: model.stars == nil) {
                    Task { await model.filter(nil) }
                }
                ForEach((1...5).reversed(), id: \.self) { stars in
                    MBChip("\(stars) ★", selected: model.stars == stars) {
                        Task { await model.filter(stars) }
                    }
                }
            }
            .padding(.vertical, 2)
        }
    }
}
