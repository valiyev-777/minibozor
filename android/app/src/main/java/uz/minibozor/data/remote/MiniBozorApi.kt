package uz.minibozor.data.remote

import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.PATCH
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Path
import retrofit2.http.Query
import uz.minibozor.data.remote.dto.*

/**
 * Every endpoint the app talks to. Ordered the same way the design's screen
 * groups are, so a screen is easy to trace to its call.
 */
interface MiniBozorApi {

    // ------------------------------------------------------------- 01-06 auth

    @POST("auth/otp/request")
    suspend fun requestOtp(@Body body: PhoneRequest): OtpRequestedDto

    @POST("auth/otp/verify")
    suspend fun verifyOtp(@Body body: OtpVerifyRequest): TokenPairDto

    @POST("auth/refresh")
    suspend fun refresh(@Body body: RefreshRequest): TokenPairDto

    @POST("auth/logout")
    suspend fun logout(): MessageDto

    @POST("auth/pin")
    suspend fun setPin(@Body body: PinChangeRequest): MessageDto

    @POST("auth/pin/verify")
    suspend fun verifyPin(@Body body: PinRequest): MessageDto

    @retrofit2.http.HTTP(method = "DELETE", path = "auth/pin", hasBody = true)
    suspend fun removePin(@Body body: PinRequest): MessageDto

    // ---------------------------------------------------------- 07-13 catalog

    @GET("home")
    suspend fun home(@Query("city") city: String = "Toshkent"): HomeDto

    @GET("categories")
    suspend fun categories(
        @Query("parent") parent: String? = null,
        @Query("quick_links") quickLinks: Boolean = false,
    ): List<CategoryDto>

    @GET("categories/{slug}")
    suspend fun category(@Path("slug") slug: String): CategoryDto

    @GET("products")
    suspend fun products(
        @Query("q") q: String? = null,
        @Query("category") category: String? = null,
        @Query("brand") brand: List<String> = emptyList(),
        @Query("min_price") minPrice: Int? = null,
        @Query("max_price") maxPrice: Int? = null,
        @Query("min_rating") minRating: Double? = null,
        @Query("size") size: List<String> = emptyList(),
        @Query("next_day_delivery") nextDayDelivery: Boolean? = null,
        @Query("free_delivery") freeDelivery: Boolean? = null,
        @Query("discounted") discounted: Boolean? = null,
        @Query("is_original") isOriginal: Boolean? = null,
        @Query("show_sold_out") showSoldOut: Boolean? = null,
        @Query("sort") sort: String = "popular",
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 20,
    ): PageDto<ProductCardDto>

    @GET("products/filters")
    suspend fun filters(@Query("category") category: String? = null): FiltersDto

    @GET("products/{id}")
    suspend fun product(@Path("id") id: Int): ProductDto

    @GET("products/{id}/similar")
    suspend fun similar(@Path("id") id: Int): List<ProductCardDto>

    @GET("brands")
    suspend fun brands(): List<BrandDto>

    // --------------------------------------------------------- 08-09 search

    @GET("search")
    suspend fun searchLanding(): SearchLandingDto

    @GET("search/suggest")
    suspend fun suggest(@Query("q") q: String): List<SuggestionDto>

    @POST("search/recent")
    suspend fun rememberSearch(@Query("query") query: String): MessageDto

    @DELETE("search/recent")
    suspend fun clearSearchHistory(): MessageDto

    // -------------------------------------------------------- 15-16 reviews

    @GET("products/{id}/reviews/summary")
    suspend fun reviewSummary(@Path("id") id: Int): ReviewSummaryDto

    @GET("products/{id}/reviews")
    suspend fun reviews(
        @Path("id") id: Int,
        @Query("stars") stars: Int? = null,
        @Query("with_photos") withPhotos: Boolean = false,
        @Query("page") page: Int = 1,
    ): PageDto<ReviewDto>

    @GET("reviews/tags")
    suspend fun reviewTags(): List<String>

    @POST("products/{id}/reviews")
    suspend fun createReview(@Path("id") id: Int, @Body body: ReviewCreateRequest): ReviewDto

    @POST("reviews/{id}/like")
    suspend fun likeReview(@Path("id") id: Int): ReviewDto

    @GET("me/reviews")
    suspend fun myReviews(@Query("page") page: Int = 1): PageDto<ReviewDto>

    @DELETE("me/reviews/{id}")
    suspend fun deleteReview(@Path("id") id: Int): MessageDto

    @GET("me/reviews/pending")
    suspend fun pendingReviews(): List<OrderItemDto>

    // ------------------------------------------------------------ 17-18 cart

    @GET("cart")
    suspend fun cart(@Query("promo_code") promoCode: String? = null): CartDto

    @POST("cart/items")
    suspend fun addToCart(@Body body: CartAddRequest): CartDto

    @PATCH("cart/items/{id}")
    suspend fun updateCartItem(@Path("id") id: Int, @Body body: CartUpdateRequest): CartDto

    @DELETE("cart/items/{id}")
    suspend fun removeCartItem(@Path("id") id: Int): CartDto

    @DELETE("cart")
    suspend fun clearCart(): CartDto

    @POST("cart/promo")
    suspend fun applyPromo(@Body body: PromoRequest): CartDto

    // -------------------------------------------------------- 35 favourites

    @GET("favorites")
    suspend fun favorites(@Query("page") page: Int = 1): PageDto<ProductCardDto>

    @PUT("favorites/{id}")
    suspend fun addFavorite(@Path("id") id: Int): MessageDto

    @DELETE("favorites/{id}")
    suspend fun removeFavorite(@Path("id") id: Int): MessageDto

    // ------------------------------------------------- 20-22, 33 delivery

    @GET("addresses")
    suspend fun addresses(): List<AddressDto>

    @POST("addresses")
    suspend fun createAddress(@Body body: AddressRequest): AddressDto

    @PUT("addresses/{id}")
    suspend fun updateAddress(@Path("id") id: Int, @Body body: AddressRequest): AddressDto

    @DELETE("addresses/{id}")
    suspend fun deleteAddress(@Path("id") id: Int): MessageDto

    @GET("delivery/slots")
    suspend fun slots(@Query("days") days: Int = 3): List<SlotDayDto>

    @GET("delivery/pickup-points")
    suspend fun pickupPoints(): List<PickupPointDto>

    // ----------------------------------------------------------- 32 cards

    @GET("payment-cards")
    suspend fun cards(): List<CardDto>

    @POST("payment-cards")
    suspend fun addCard(@Body body: CardRequest): CardDto

    @POST("payment-cards/{id}/default")
    suspend fun makeCardDefault(@Path("id") id: Int): CardDto

    @DELETE("payment-cards/{id}")
    suspend fun deleteCard(@Path("id") id: Int): MessageDto

    // -------------------------------------------------------- 19, 23-29 orders

    @POST("checkout/preview")
    suspend fun checkoutPreview(@Body body: CheckoutRequest): CheckoutPreviewDto

    @POST("orders")
    suspend fun createOrder(@Body body: CheckoutRequest): OrderDto

    @GET("orders")
    suspend fun orders(
        @Query("active") active: Boolean? = null,
        @Query("page") page: Int = 1,
    ): PageDto<OrderSummaryDto>

    @GET("orders/{id}")
    suspend fun order(@Path("id") id: Int): OrderDto

    @POST("orders/{id}/cancel")
    suspend fun cancelOrder(@Path("id") id: Int, @Body body: CancelRequest): OrderDto

    @POST("orders/{id}/return")
    suspend fun requestReturn(@Path("id") id: Int, @Body body: ReturnRequestBody): ReturnDto

    @GET("returns")
    suspend fun returns(): List<ReturnDto>

    @GET("orders/reasons/cancel")
    suspend fun cancelReasons(): List<ReasonDto>

    @GET("orders/reasons/return")
    suspend fun returnReasons(): List<ReasonDto>

    // ------------------------------------------------------ 30-31, 36-40 me

    @GET("me")
    suspend fun me(): UserDto

    @PATCH("me")
    suspend fun updateMe(@Body body: UserUpdateRequest): UserDto

    @GET("me/overview")
    suspend fun overview(): ProfileOverviewDto

    @GET("me/settings")
    suspend fun settings(): SettingsDto

    @PUT("me/settings")
    suspend fun updateSettings(@Body body: SettingsRequest): SettingsDto

    @GET("me/notification-prefs")
    suspend fun notificationPrefs(): NotificationPrefsDto

    @PUT("me/notification-prefs")
    suspend fun updateNotificationPrefs(@Body body: NotificationPrefsRequest): NotificationPrefsDto

    @PUT("me/biometrics")
    suspend fun setBiometrics(@Query("enabled") enabled: Boolean): UserDto

    @DELETE("me")
    suspend fun deleteAccount(): MessageDto

    @GET("notifications")
    suspend fun notifications(): List<NotificationGroupDto>

    @GET("notifications/unread-count")
    suspend fun unreadCount(): Map<String, Int>

    @POST("notifications/read")
    suspend fun markNotificationsRead(): MessageDto

    @DELETE("notifications/{id}")
    suspend fun deleteNotification(@Path("id") id: Int): MessageDto

    // ------------------------------------------------------- 39, 45-46 content

    @GET("help/faq")
    suspend fun faq(): List<FaqDto>

    @GET("help/support")
    suspend fun support(): Map<String, String>

    @GET("legal")
    suspend fun legalDocs(): List<LegalDocDto>

    @GET("legal/{slug}")
    suspend fun legalDoc(@Path("slug") slug: String): LegalDocFullDto

    @GET("languages")
    suspend fun languages(): List<Map<String, String>>
}
