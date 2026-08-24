import Foundation

/// Everything the listing and the filter sheet agree on. A value type, so the
/// sheet can edit a draft and only commit on "Qo'llash".
struct ProductQuery: Equatable {
    var text: String?
    var category: String?
    var brands: Set<String> = []
    var sizes: Set<String> = []
    var minPrice: Int?
    var maxPrice: Int?
    var minRating: Double?
    var flags: [String: Bool] = [:]
    var sort: String = "popular"

    /// Drives the "N ta filtr" badge on the listing toolbar.
    var activeFilterCount: Int {
        brands.count
            + sizes.count
            + flags.values.filter { $0 }.count
            + ((minPrice != nil || maxPrice != nil) ? 1 : 0)
            + (minRating != nil ? 1 : 0)
    }

    mutating func toggleBrand(_ slug: String) {
        if brands.contains(slug) { brands.remove(slug) } else { brands.insert(slug) }
    }

    mutating func toggleSize(_ label: String) {
        if sizes.contains(label) { sizes.remove(label) } else { sizes.insert(label) }
    }

    mutating func toggleFlag(_ key: String) {
        flags[key] = !(flags[key] ?? false)
    }

    func cleared() -> ProductQuery {
        ProductQuery(text: text, category: category, sort: sort)
    }

    func queryItems(page: Int) -> [URLQueryItem] {
        var items: [URLQueryItem] = [
            URLQueryItem(name: "page", value: String(page)),
            URLQueryItem(name: "sort", value: sort),
        ]
        if let text, !text.isEmpty { items.append(URLQueryItem(name: "q", value: text)) }
        if let category, !category.isEmpty { items.append(URLQueryItem(name: "category", value: category)) }
        for brand in brands.sorted() { items.append(URLQueryItem(name: "brand", value: brand)) }
        for size in sizes.sorted() { items.append(URLQueryItem(name: "size", value: size)) }
        if let minPrice { items.append(URLQueryItem(name: "min_price", value: String(minPrice))) }
        if let maxPrice { items.append(URLQueryItem(name: "max_price", value: String(maxPrice))) }
        if let minRating { items.append(URLQueryItem(name: "min_rating", value: String(minRating))) }
        for (key, value) in flags where value {
            items.append(URLQueryItem(name: key, value: "true"))
        }
        return items
    }
}
