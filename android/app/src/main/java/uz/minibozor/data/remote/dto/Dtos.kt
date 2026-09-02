package uz.minibozor.data.remote.dto

import androidx.compose.runtime.Immutable
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

// --------------------------------------------------------------------- shared

@Immutable
@Serializable
data class PageDto<T>(
    val items: List<T>,
    val page: Int,
    @SerialName("page_size") val pageSize: Int,
    val total: Int,
    @SerialName("has_more") val hasMore: Boolean,
)

@Immutable
@Serializable
data class MessageDto(val ok: Boolean = true, val message: String = "")

// ----------------------------------------------------------------------- auth

@Immutable
@Serializable
data class PhoneRequest(val phone: String)

@Immutable
@Serializable
data class OtpRequestedDto(
    val phone: String,
    @SerialName("expires_in") val expiresIn: Int,
    @SerialName("resend_after") val resendAfter: Int,
    @SerialName("dev_code") val devCode: String? = null,
)

@Immutable
@Serializable
data class OtpVerifyRequest(val phone: String, val code: String)

@Immutable
@Serializable
data class TokenPairDto(
    @SerialName("access_token") val accessToken: String,
    @SerialName("refresh_token") val refreshToken: String,
    @SerialName("expires_in") val expiresIn: Int,
    @SerialName("is_new_user") val isNewUser: Boolean = false,
)

@Immutable
@Serializable
data class RefreshRequest(@SerialName("refresh_token") val refreshToken: String)

@Immutable
@Serializable
data class PinRequest(val pin: String)

@Immutable
@Serializable
data class PinChangeRequest(
    @SerialName("current_pin") val currentPin: String? = null,
    @SerialName("new_pin") val newPin: String,
)

// ----------------------------------------------------------------------- user

@Immutable
@Serializable
data class UserDto(
    val id: Int,
    val phone: String,
    @SerialName("full_name") val fullName: String,
    val email: String? = null,
    @SerialName("birth_date") val birthDate: String? = null,
    val gender: String? = null,
    @SerialName("avatar_url") val avatarUrl: String? = null,
    val language: String,
    @SerialName("has_pin") val hasPin: Boolean,
    @SerialName("biometrics_enabled") val biometricsEnabled: Boolean,
)

@Immutable
@Serializable
data class UserUpdateRequest(
    @SerialName("full_name") val fullName: String? = null,
    val email: String? = null,
    @SerialName("birth_date") val birthDate: String? = null,
    val gender: String? = null,
)

@Immutable
@Serializable
data class SettingsDto(
    val language: String,
    @SerialName("location_enabled") val locationEnabled: Boolean,
    @SerialName("night_mode") val nightMode: Boolean,
)

@Immutable
@Serializable
data class SettingsRequest(
    val language: String? = null,
    @SerialName("location_enabled") val locationEnabled: Boolean? = null,
    @SerialName("night_mode") val nightMode: Boolean? = null,
)

@Immutable
@Serializable
data class NotificationPrefsDto(
    @SerialName("order_status") val orderStatus: Boolean,
    val promotions: Boolean,
    @SerialName("price_drop") val priceDrop: Boolean,
    val push: Boolean,
    val sms: Boolean,
)

@Immutable
@Serializable
data class NotificationPrefsRequest(
    @SerialName("order_status") val orderStatus: Boolean? = null,
    val promotions: Boolean? = null,
    @SerialName("price_drop") val priceDrop: Boolean? = null,
    val push: Boolean? = null,
    val sms: Boolean? = null,
)

@Immutable
@Serializable
data class ProfileOverviewDto(
    val user: UserDto,
    @SerialName("orders_count") val ordersCount: Int,
    @SerialName("favorites_count") val favoritesCount: Int,
    @SerialName("reviews_count") val reviewsCount: Int,
    @SerialName("addresses_count") val addressesCount: Int,
    @SerialName("cards_count") val cardsCount: Int,
    @SerialName("unread_notifications") val unreadNotifications: Int,
)

// -------------------------------------------------------------------- catalog

@Immutable
@Serializable
data class CategoryDto(
    val id: Int,
    val slug: String,
    val name: String,
    val subtitle: String = "",
    val icon: String = "box",
    @SerialName("image_url") val imageUrl: String? = null,
    @SerialName("product_count") val productCount: Int = 0,
    @SerialName("has_children") val hasChildren: Boolean = false,
)

@Immutable
@Serializable
data class BrandDto(
    val id: Int,
    val slug: String,
    val name: String,
    @SerialName("product_count") val productCount: Int = 0,
)

@Immutable
@Serializable
data class VariantDto(
    val id: Int,
    val kind: String,
    val label: String,
    val value: String,
    /**
     * The product photographed in this colour, when the shop supplied one.
     *
     * A colour is chosen by looking at the thing rather than at a hex circle,
     * so the picker draws this when it is there and falls back to [value] when
     * it is not. Always null on a size.
     */
    @SerialName("image_url") val imageUrl: String? = null,
    @SerialName("in_stock") val inStock: Boolean,
)

@Immutable
@Serializable
data class SpecDto(val key: String, val value: String)

@Immutable
@Serializable
data class ProductCardDto(
    val id: Int,
    val title: String,
    val price: Int,
    @SerialName("old_price") val oldPrice: Int? = null,
    @SerialName("discount_percent") val discountPercent: Int? = null,
    @SerialName("image_url") val imageUrl: String? = null,
    val rating: Double = 0.0,
    @SerialName("reviews_count") val reviewsCount: Int = 0,
    val badge: String? = null,
    @SerialName("in_stock") val inStock: Boolean = true,
    @SerialName("is_favorite") val isFavorite: Boolean = false,
    /** Whether tapping "Savatga" should open the picker sheet or add at once. */
    @SerialName("has_variants") val hasVariants: Boolean = false,
)

@Immutable
@Serializable
data class ProductDto(
    val id: Int,
    val sku: String,
    val title: String,
    val subtitle: String = "",
    val description: String = "",
    val price: Int,
    @SerialName("old_price") val oldPrice: Int? = null,
    @SerialName("discount_percent") val discountPercent: Int? = null,
    @SerialName("image_url") val imageUrl: String? = null,
    val images: List<String> = emptyList(),
    val rating: Double = 0.0,
    @SerialName("reviews_count") val reviewsCount: Int = 0,
    val badge: String? = null,
    @SerialName("in_stock") val inStock: Boolean = true,
    @SerialName("is_favorite") val isFavorite: Boolean = false,
    val category: CategoryDto,
    val brand: BrandDto? = null,
    val variants: List<VariantDto> = emptyList(),
    val specs: List<SpecDto> = emptyList(),
    val seller: String = "",
    val warranty: String? = null,
    @SerialName("stock_left") val stockLeft: Int = 0,
    @SerialName("is_original") val isOriginal: Boolean = true,
    @SerialName("free_delivery") val freeDelivery: Boolean = true,
    @SerialName("next_day_delivery") val nextDayDelivery: Boolean = true,
    @SerialName("delivery_note") val deliveryNote: String = "",
    /** How many have been sold — printed beside the rating. */
    @SerialName("sold_count") val soldCount: Int = 0,
)

@Immutable
@Serializable
data class BannerDto(
    val id: Int,
    val kicker: String = "",
    val title: String,
    val subtitle: String = "",
    val cta: String = "",
    @SerialName("image_url") val imageUrl: String,
    @SerialName("gradient_from") val gradientFrom: String,
    @SerialName("gradient_to") val gradientTo: String,
    @SerialName("target_type") val targetType: String,
    @SerialName("target_value") val targetValue: String,
)

@Immutable
@Serializable
data class SectionDto(
    val key: String,
    val title: String,
    val subtitle: String = "",
    val layout: String,
    @SerialName("category_slug") val categorySlug: String? = null,
    val products: List<ProductCardDto> = emptyList(),
)

@Immutable
@Serializable
data class HomeDto(
    val city: String,
    val banners: List<BannerDto>,
    val categories: List<CategoryDto>,
    val sections: List<SectionDto>,
)

@Immutable
@Serializable
data class FilterFlagDto(
    val key: String,
    val label: String,
    val subtitle: String = "",
    val count: Int = 0,
)

@Immutable
@Serializable
data class FiltersDto(
    @SerialName("price_min") val priceMin: Int,
    @SerialName("price_max") val priceMax: Int,
    val brands: List<BrandDto>,
    val sizes: List<String>,
    val ratings: List<String>,
    val flags: List<FilterFlagDto>,
    val sorts: List<Map<String, String>>,
)

@Immutable
@Serializable
data class SuggestionDto(
    @SerialName("product_id") val productId: Int,
    val title: String,
    val price: Int,
    @SerialName("image_url") val imageUrl: String? = null,
)

@Immutable
@Serializable
data class SearchLandingDto(val recent: List<String>, val popular: List<String>)

// -------------------------------------------------------------------- reviews

@Immutable
@Serializable
data class RatingBucketDto(val stars: Int, val count: Int, val percent: Int)

@Immutable
@Serializable
data class ReviewSummaryDto(
    val rating: Double,
    val total: Int,
    val distribution: List<RatingBucketDto>,
    /** A few customer photographs for the strip beside the rating. */
    val photos: List<String> = emptyList(),
    @SerialName("photos_total") val photosTotal: Int = 0,
)

@Immutable
@Serializable
data class ReviewDto(
    val id: Int,
    @SerialName("author_name") val authorName: String,
    @SerialName("author_initials") val authorInitials: String,
    val rating: Int,
    val text: String = "",
    @SerialName("variant_label") val variantLabel: String = "",
    val tags: List<String> = emptyList(),
    val photos: List<String> = emptyList(),
    val likes: Int = 0,
    @SerialName("liked_by_me") val likedByMe: Boolean = false,
    val status: String,
    @SerialName("created_at") val createdAt: String,
    val product: ProductCardDto? = null,
)

@Immutable
@Serializable
data class ReviewCreateRequest(
    val rating: Int,
    val text: String = "",
    val tags: List<String> = emptyList(),
    val photos: List<String> = emptyList(),
    @SerialName("variant_label") val variantLabel: String = "",
    @SerialName("order_item_id") val orderItemId: Int? = null,
)

// ----------------------------------------------------------------------- cart

@Immutable
@Serializable
data class CartItemDto(
    val id: Int,
    @SerialName("product_id") val productId: Int,
    val title: String,
    @SerialName("image_url") val imageUrl: String? = null,
    @SerialName("variant_label") val variantLabel: String = "",
    @SerialName("unit_price") val unitPrice: Int,
    @SerialName("old_unit_price") val oldUnitPrice: Int? = null,
    val quantity: Int,
    val selected: Boolean,
    @SerialName("in_stock") val inStock: Boolean,
    @SerialName("line_total") val lineTotal: Int,
)

@Immutable
@Serializable
data class CartTotalsDto(
    @SerialName("items_count") val itemsCount: Int,
    val subtotal: Int,
    val discount: Int,
    @SerialName("delivery_fee") val deliveryFee: Int,
    val total: Int,
    @SerialName("free_delivery_threshold") val freeDeliveryThreshold: Int,
    @SerialName("promo_code") val promoCode: String? = null,
)

@Immutable
@Serializable
data class CartDto(val items: List<CartItemDto>, val totals: CartTotalsDto)

@Immutable
@Serializable
data class CartAddRequest(
    @SerialName("product_id") val productId: Int,
    @SerialName("variant_id") val variantId: Int? = null,
    @SerialName("color_variant_id") val colorVariantId: Int? = null,
    val quantity: Int = 1,
)

@Immutable
@Serializable
data class CartUpdateRequest(val quantity: Int? = null, val selected: Boolean? = null)

@Immutable
@Serializable
data class PromoRequest(val code: String)

// ------------------------------------------------------------------- delivery

@Immutable
@Serializable
data class AddressDto(
    val id: Int,
    val title: String,
    val icon: String = "pin",
    val badge: String? = null,
    val line: String,
    val city: String = "",
    val meta: String = "",
    val floor: String? = null,
    val apartment: String? = null,
    @SerialName("entrance_code") val entranceCode: String? = null,
    val comment: String? = null,
    val latitude: Double? = null,
    val longitude: Double? = null,
    @SerialName("is_default") val isDefault: Boolean = false,
)

@Immutable
@Serializable
data class AddressRequest(
    val title: String = "Uy",
    val icon: String = "pin",
    val badge: String? = null,
    val line: String,
    val city: String = "Toshkent",
    val floor: String? = null,
    val apartment: String? = null,
    @SerialName("entrance_code") val entranceCode: String? = null,
    val comment: String? = null,
    val latitude: Double? = null,
    val longitude: Double? = null,
    @SerialName("is_default") val isDefault: Boolean = false,
)

@Immutable
@Serializable
data class PickupPointDto(
    val id: Int,
    val name: String,
    val address: String = "",
    val hours: String = "",
    @SerialName("distance_km") val distanceKm: Double? = null,
)

@Immutable
@Serializable
data class SlotDto(
    val id: Int,
    val day: String,
    @SerialName("start_time") val startTime: String,
    @SerialName("end_time") val endTime: String,
    val label: String,
    val note: String = "",
    val price: Int = 0,
    val express: Boolean = false,
    val available: Boolean = true,
)

@Immutable
@Serializable
data class SlotDayDto(
    val day: String,
    @SerialName("weekday_label") val weekdayLabel: String,
    @SerialName("day_label") val dayLabel: String,
    @SerialName("month_label") val monthLabel: String,
    val slots: List<SlotDto>,
)

// -------------------------------------------------------------------- payment

@Immutable
@Serializable
data class CardDto(
    val id: Int,
    val brand: String,
    val last4: String,
    val holder: String = "",
    val expiry: String,
    val status: String,
    @SerialName("is_default") val isDefault: Boolean = false,
)

@Immutable
@Serializable
data class CardRequest(
    val brand: String,
    val last4: String,
    val holder: String = "",
    @SerialName("expiry_month") val expiryMonth: Int,
    @SerialName("expiry_year") val expiryYear: Int,
    @SerialName("processor_token") val processorToken: String,
    @SerialName("is_default") val isDefault: Boolean = false,
)

// --------------------------------------------------------------------- orders

@Immutable
@Serializable
data class OrderItemDto(
    val id: Int,
    @SerialName("product_id") val productId: Int? = null,
    val title: String,
    @SerialName("image_url") val imageUrl: String = "",
    @SerialName("variant_label") val variantLabel: String = "",
    @SerialName("unit_price") val unitPrice: Int,
    val quantity: Int,
    @SerialName("line_total") val lineTotal: Int,
    val reviewed: Boolean = false,
)

@Immutable
@Serializable
data class OrderEventDto(
    val status: String,
    val title: String,
    @SerialName("happened_at") val happenedAt: String? = null,
    val note: String = "",
    val done: Boolean = false,
)

@Immutable
@Serializable
data class OrderSummaryDto(
    val id: Int,
    val code: String,
    val status: String,
    @SerialName("status_label") val statusLabel: String,
    val total: Int,
    @SerialName("items_count") val itemsCount: Int,
    @SerialName("preview_images") val previewImages: List<String> = emptyList(),
    @SerialName("eta_label") val etaLabel: String = "",
    @SerialName("created_at") val createdAt: String,
    @SerialName("can_cancel") val canCancel: Boolean = false,
    @SerialName("can_track") val canTrack: Boolean = false,
)

@Immutable
@Serializable
data class OrderDto(
    val id: Int,
    val code: String,
    val status: String,
    @SerialName("status_label") val statusLabel: String,
    val total: Int,
    @SerialName("items_count") val itemsCount: Int,
    @SerialName("preview_images") val previewImages: List<String> = emptyList(),
    @SerialName("eta_label") val etaLabel: String = "",
    @SerialName("created_at") val createdAt: String,
    @SerialName("can_cancel") val canCancel: Boolean = false,
    @SerialName("can_track") val canTrack: Boolean = false,
    @SerialName("delivery_kind") val deliveryKind: String,
    @SerialName("address_line") val addressLine: String = "",
    @SerialName("address_meta") val addressMeta: String = "",
    @SerialName("delivery_day") val deliveryDay: String? = null,
    @SerialName("delivery_start") val deliveryStart: String? = null,
    @SerialName("delivery_end") val deliveryEnd: String? = null,
    @SerialName("payment_method") val paymentMethod: String,
    @SerialName("payment_label") val paymentLabel: String = "",
    val paid: Boolean = false,
    @SerialName("recipient_name") val recipientName: String = "",
    @SerialName("recipient_phone") val recipientPhone: String = "",
    val subtotal: Int = 0,
    @SerialName("delivery_fee") val deliveryFee: Int = 0,
    val discount: Int = 0,
    val items: List<OrderItemDto> = emptyList(),
    val events: List<OrderEventDto> = emptyList(),
)

@Immutable
@Serializable
data class CheckoutRequest(
    @SerialName("address_id") val addressId: Int? = null,
    @SerialName("pickup_point_id") val pickupPointId: Int? = null,
    @SerialName("slot_id") val slotId: Int? = null,
    @SerialName("payment_method") val paymentMethod: String = "card",
    @SerialName("payment_card_id") val paymentCardId: Int? = null,
    @SerialName("recipient_name") val recipientName: String = "",
    @SerialName("recipient_phone") val recipientPhone: String = "",
    @SerialName("promo_code") val promoCode: String? = null,
    val comment: String = "",
)

@Immutable
@Serializable
data class CheckoutPreviewDto(
    val items: List<CartItemDto>,
    val address: AddressDto? = null,
    @SerialName("pickup_point") val pickupPoint: PickupPointDto? = null,
    val slot: SlotDto? = null,
    val card: CardDto? = null,
    val totals: CartTotalsDto,
)

@Immutable
@Serializable
data class ReasonDto(
    val id: Int,
    val label: String,
    @SerialName("requires_comment") val requiresComment: Boolean = false,
)

@Immutable
@Serializable
data class CancelRequest(
    @SerialName("reason_id") val reasonId: Int? = null,
    val reason: String = "",
    val comment: String = "",
)

@Immutable
@Serializable
data class ReturnRequestBody(
    @SerialName("order_item_id") val orderItemId: Int? = null,
    @SerialName("reason_id") val reasonId: Int? = null,
    val reason: String = "",
    val comment: String = "",
    val photos: List<String> = emptyList(),
)

@Immutable
@Serializable
data class ReturnDto(
    val id: Int,
    @SerialName("order_code") val orderCode: String,
    val reason: String,
    val comment: String = "",
    val status: String,
    @SerialName("created_at") val createdAt: String,
)

// ----------------------------------------------------------------------- misc

@Immutable
@Serializable
data class NotificationDto(
    val id: Int,
    val kind: String,
    val icon: String,
    val title: String,
    val text: String = "",
    @SerialName("deep_link") val deepLink: String? = null,
    val read: Boolean = false,
    @SerialName("created_at") val createdAt: String,
)

@Immutable
@Serializable
data class NotificationGroupDto(val label: String, val items: List<NotificationDto>)

@Immutable
@Serializable
data class FaqDto(val id: Int, val question: String, val answer: String = "")

@Immutable
@Serializable
data class LegalDocDto(
    val slug: String,
    val icon: String,
    val title: String,
    val meta: String = "",
)

@Immutable
@Serializable
data class LegalDocFullDto(
    val slug: String,
    val icon: String,
    val title: String,
    val meta: String = "",
    val body: String = "",
)
