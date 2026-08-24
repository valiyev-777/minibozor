import Foundation

/// Screens 07–16 and 35.
struct CatalogRepository {
    private let api = APIClient.shared

    func home(city: String) async -> Outcome<HomeDTO> {
        await run { try await api.get("home", query: [URLQueryItem(name: "city", value: city)]) }
    }

    func rootCategories() async -> Outcome<[CategoryDTO]> {
        await run { try await api.get("categories") }
    }

    func children(of slug: String) async -> Outcome<[CategoryDTO]> {
        await run { try await api.get("categories", query: [URLQueryItem(name: "parent", value: slug)]) }
    }

    func category(_ slug: String) async -> Outcome<CategoryDTO> {
        await run { try await api.get("categories/\(slug)") }
    }

    func products(_ query: ProductQuery, page: Int) async -> Outcome<PageDTO<ProductCardDTO>> {
        await run { try await api.get("products", query: query.queryItems(page: page)) }
    }

    func filters(category: String?) async -> Outcome<FiltersDTO> {
        let items = category.map { [URLQueryItem(name: "category", value: $0)] } ?? []
        return await run { try await api.get("products/filters", query: items) }
    }

    func product(_ id: Int) async -> Outcome<ProductDTO> {
        await run { try await api.get("products/\(id)") }
    }

    func similar(to id: Int) async -> Outcome<[ProductCardDTO]> {
        await run { try await api.get("products/\(id)/similar") }
    }

    func searchLanding() async -> Outcome<SearchLandingDTO> {
        await run { try await api.get("search") }
    }

    func suggest(_ text: String) async -> Outcome<[SuggestionDTO]> {
        await run { try await api.get("search/suggest", query: [URLQueryItem(name: "q", value: text)]) }
    }

    func rememberSearch(_ text: String) async {
        let _: MessageDTO? = try? await api.post(
            "search/recent",
            query: [URLQueryItem(name: "query", value: text)]
        )
    }

    func clearSearchHistory() async {
        let _: MessageDTO? = try? await api.delete("search/recent")
    }

    func reviewSummary(productId: Int) async -> Outcome<ReviewSummaryDTO> {
        await run { try await api.get("products/\(productId)/reviews/summary") }
    }

    func reviews(productId: Int, stars: Int?, page: Int) async -> Outcome<PageDTO<ReviewDTO>> {
        var items = [URLQueryItem(name: "page", value: String(page))]
        if let stars { items.append(URLQueryItem(name: "stars", value: String(stars))) }
        return await run { try await api.get("products/\(productId)/reviews", query: items) }
    }

    func reviewTags() async -> Outcome<[String]> {
        await run { try await api.get("reviews/tags") }
    }

    func createReview(productId: Int, body: ReviewCreateRequest) async -> Outcome<ReviewDTO> {
        await run { try await api.post("products/\(productId)/reviews", body: body) }
    }

    func likeReview(_ id: Int) async -> Outcome<ReviewDTO> {
        await run { try await api.post("reviews/\(id)/like") }
    }

    func favorites(page: Int = 1) async -> Outcome<PageDTO<ProductCardDTO>> {
        await run { try await api.get("favorites", query: [URLQueryItem(name: "page", value: String(page))]) }
    }

    func setFavorite(productId: Int, favorite: Bool) async -> Outcome<Void> {
        await run {
            if favorite {
                let _: MessageDTO = try await api.put("favorites/\(productId)")
            } else {
                let _: MessageDTO = try await api.delete("favorites/\(productId)")
            }
        }
    }
}
