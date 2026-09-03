package uz.minibozor.data.repository

import uz.minibozor.core.util.Outcome
import uz.minibozor.core.util.apiCall
import uz.minibozor.data.remote.MiniBozorApi
import uz.minibozor.data.remote.dto.*
import uz.minibozor.ui.catalog.ProductQuery
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class CatalogRepository @Inject constructor(private val api: MiniBozorApi) {

    suspend fun home(city: String): Outcome<HomeDto> = apiCall { api.home(city) }

    suspend fun rootCategories(): Outcome<List<CategoryDto>> = apiCall { api.categories() }

    suspend fun children(parent: String): Outcome<List<CategoryDto>> =
        apiCall { api.categories(parent = parent) }

    suspend fun category(slug: String): Outcome<CategoryDto> = apiCall { api.category(slug) }

    suspend fun products(query: ProductQuery, page: Int): Outcome<PageDto<ProductCardDto>> =
        apiCall {
            api.products(
                q = query.text,
                category = query.category,
                brand = query.brands.toList(),
                minPrice = query.minPrice,
                maxPrice = query.maxPrice,
                minRating = query.minRating,
                size = query.sizes.toList(),
                nextDayDelivery = query.flags["next_day_delivery"],
                freeDelivery = query.flags["free_delivery"],
                discounted = query.flags["discounted"],
                isOriginal = query.flags["is_original"],
                // Only ever sent when it is on: the server leaves them out by
                // default, and a `false` on every request is noise.
                showSoldOut = true.takeIf { query.showSoldOut },
                sort = query.sort,
                page = page,
            )
        }

    suspend fun filters(category: String?): Outcome<FiltersDto> = apiCall { api.filters(category) }

    suspend fun product(id: Int): Outcome<ProductDto> = apiCall { api.product(id) }

    suspend fun similar(id: Int): Outcome<List<ProductCardDto>> = apiCall { api.similar(id) }

    suspend fun searchLanding(): Outcome<SearchLandingDto> = apiCall { api.searchLanding() }

    suspend fun suggest(q: String): Outcome<List<SuggestionDto>> = apiCall { api.suggest(q) }

    suspend fun rememberSearch(q: String) = apiCall { api.rememberSearch(q) }

    suspend fun clearSearchHistory() = apiCall { api.clearSearchHistory() }

    suspend fun reviewSummary(productId: Int): Outcome<ReviewSummaryDto> =
        apiCall { api.reviewSummary(productId) }

    suspend fun reviews(productId: Int, stars: Int?, page: Int): Outcome<PageDto<ReviewDto>> =
        apiCall { api.reviews(productId, stars, page = page) }

    suspend fun reviewTags(): Outcome<List<String>> = apiCall { api.reviewTags() }

    suspend fun createReview(productId: Int, body: ReviewCreateRequest): Outcome<ReviewDto> =
        apiCall { api.createReview(productId, body) }

    suspend fun likeReview(reviewId: Int): Outcome<ReviewDto> = apiCall { api.likeReview(reviewId) }

    suspend fun favorites(page: Int): Outcome<PageDto<ProductCardDto>> =
        apiCall { api.favorites(page) }

    suspend fun setFavorite(productId: Int, favorite: Boolean): Outcome<Unit> =
        apiCall { if (favorite) api.addFavorite(productId) else api.removeFavorite(productId) }
            .let { if (it is Outcome.Failure) it else Outcome.Success(Unit) }
}
