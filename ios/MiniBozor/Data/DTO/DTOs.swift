import Foundation

// The decoder uses `.convertFromSnakeCase`, so these stay plain camelCase and
// need no CodingKeys.

// MARK: - Shared

struct PageDTO<T: Decodable>: Decodable {
    let items: [T]
    let page: Int
    let pageSize: Int
    let total: Int
    let hasMore: Bool
}

struct MessageDTO: Decodable {
    let ok: Bool
    let message: String
}

// MARK: - Auth

struct PhoneRequest: Encodable {
    let phone: String
}

struct OtpRequestedDTO: Decodable {
    let phone: String
    let expiresIn: Int
    let resendAfter: Int
    /// Only populated by dev builds of the backend.
    let devCode: String?
}

struct OtpVerifyRequest: Encodable {
    let phone: String
    let code: String
}

struct TokenPairDTO: Decodable {
    let accessToken: String
    let refreshToken: String
    let expiresIn: Int
    let isNewUser: Bool?
}

struct RefreshRequest: Encodable {
    let refreshToken: String
}

struct PinRequest: Encodable {
    let pin: String
}

struct PinChangeRequest: Encodable {
    let currentPin: String?
    let newPin: String
}

// MARK: - User

struct UserDTO: Decodable, Identifiable, Equatable {
    let id: Int
    let phone: String
    let fullName: String
    let email: String?
    let birthDate: String?
    let gender: String?
    let avatarUrl: String?
    let language: String
    let hasPin: Bool
    let biometricsEnabled: Bool
}

struct UserUpdateRequest: Encodable {
    var fullName: String?
    var email: String?
    var birthDate: String?
    var gender: String?
}

struct SettingsDTO: Decodable, Equatable {
    let language: String
    let locationEnabled: Bool
    let nightMode: Bool
}

struct SettingsRequest: Encodable {
    var language: String?
    var locationEnabled: Bool?
    var nightMode: Bool?
}

struct NotificationPrefsDTO: Decodable, Equatable {
    let orderStatus: Bool
    let promotions: Bool
    let priceDrop: Bool
    let push: Bool
    let sms: Bool
}

struct NotificationPrefsRequest: Encodable {
    var orderStatus: Bool?
    var promotions: Bool?
    var priceDrop: Bool?
    var push: Bool?
    var sms: Bool?
}

struct ProfileOverviewDTO: Decodable {
    let user: UserDTO
    let ordersCount: Int
    let favoritesCount: Int
    let reviewsCount: Int
    let addressesCount: Int
    let cardsCount: Int
    let unreadNotifications: Int
}

// MARK: - Catalog

struct CategoryDTO: Decodable, Identifiable, Hashable {
    let id: Int
    let slug: String
    let name: String
    let subtitle: String
    let icon: String
    let imageUrl: String?
    let productCount: Int
    let hasChildren: Bool
}

struct BrandDTO: Decodable, Identifiable, Hashable {
    let id: Int
    let slug: String
    let name: String
    let productCount: Int
}

struct VariantDTO: Decodable, Identifiable, Hashable {
    let id: Int
    let kind: String
    let label: String
    let value: String
    /// The product photographed in this colour, so the picker can show the
    /// thing rather than ask the customer to imagine what `#0E0F12` looks like
    /// on a shoe. None for sizes, and for a colour nobody photographed.
    ///
    /// Optional rather than defaulted: a synthesised `Decodable` only falls
    /// back for optionals, so this is also what keeps an older backend from
    /// failing the whole product page over one missing key.
    let imageUrl: String?
    let inStock: Bool
}

struct SpecDTO: Decodable, Hashable {
    let key: String
    let value: String
}

struct ProductCardDTO: Decodable, Identifiable, Hashable {
    let id: Int
    let title: String
    let price: Int
    let oldPrice: Int?
    let discountPercent: Int?
    let imageUrl: String?
    let rating: Double
    let reviewsCount: Int
    let badge: String?
    let inStock: Bool
    var isFavorite: Bool
    /// How many are left, so a tile can say when there are few.
    var stockLeft: Int = 0
    /// Whether tapping "Savatga" should open the picker sheet or add at once.
    var hasVariants: Bool = false
}

struct ProductDTO: Decodable, Identifiable {
    let id: Int
    let sku: String
    let title: String
    let subtitle: String
    let description: String
    let price: Int
    let oldPrice: Int?
    let discountPercent: Int?
    let imageUrl: String?
    let images: [String]
    let rating: Double
    let reviewsCount: Int
    let badge: String?
    let inStock: Bool
    var isFavorite: Bool
    let category: CategoryDTO
    let brand: BrandDTO?
    let variants: [VariantDTO]
    let specs: [SpecDTO]
    let seller: String
    let warranty: String?
    let stockLeft: Int
    let isOriginal: Bool
    let freeDelivery: Bool
    let nextDayDelivery: Bool
    let deliveryNote: String
    /// How many have been sold. The page prints it beside the rating, where
    /// "2 010 ta buyurtma" is the strongest thing on the panel.
    let soldCount: Int?

    var sizes: [VariantDTO] { variants.filter { $0.kind == "size" } }
    var colors: [VariantDTO] { variants.filter { $0.kind == "color" } }
    var sold: Int { soldCount ?? 0 }
}

struct BannerDTO: Decodable, Identifiable, Hashable {
    let id: Int
    let kicker: String
    let title: String
    let subtitle: String
    let cta: String
    let imageUrl: String
    let gradientFrom: String
    let gradientTo: String
    let targetType: String
    let targetValue: String
}

struct SectionDTO: Decodable, Identifiable {
    var id: String { key }
    let key: String
    let title: String
    let subtitle: String
    let layout: String
    let categorySlug: String?
    let products: [ProductCardDTO]
}

struct HomeDTO: Decodable {
    let city: String
    let banners: [BannerDTO]
    let categories: [CategoryDTO]
    let sections: [SectionDTO]
}

struct FilterFlagDTO: Decodable, Identifiable, Hashable {
    var id: String { key }
    let key: String
    let label: String
    let subtitle: String
    let count: Int
}

struct FiltersDTO: Decodable {
    let priceMin: Int
    let priceMax: Int
    let brands: [BrandDTO]
    let sizes: [String]
    let ratings: [String]
    let flags: [FilterFlagDTO]
    let sorts: [[String: String]]
}

struct SuggestionDTO: Decodable, Identifiable {
    var id: Int { productId }
    let productId: Int
    let title: String
    let price: Int
    let imageUrl: String?
}

struct SearchLandingDTO: Decodable {
    let recent: [String]
    let popular: [String]
}

// MARK: - Reviews

struct RatingBucketDTO: Decodable, Identifiable {
    var id: Int { stars }
    let stars: Int
    let count: Int
    let percent: Int
}

struct ReviewSummaryDTO: Decodable {
    let rating: Double
    let total: Int
    let distribution: [RatingBucketDTO]
    /// A handful of customer photographs for the strip beside the rating, and
    /// the full count so the last tile can say how many more there are.
    let photos: [String]?
    let photosTotal: Int?

    var photoStrip: [String] { photos ?? [] }
    var photoCount: Int { photosTotal ?? 0 }
}

struct ReviewDTO: Decodable, Identifiable {
    let id: Int
    let authorName: String
    let authorInitials: String
    let rating: Int
    let text: String
    let variantLabel: String
    let tags: [String]
    let photos: [String]
    let likes: Int
    let likedByMe: Bool
    let status: String
    let createdAt: String
    let product: ProductCardDTO?
}

struct ReviewCreateRequest: Encodable {
    let rating: Int
    let text: String
    let tags: [String]
    let photos: [String]
    let variantLabel: String
    let orderItemId: Int?
}

// MARK: - Cart

struct CartItemDTO: Decodable, Identifiable, Hashable {
    let id: Int
    let productId: Int
    let title: String
    let imageUrl: String?
    let variantLabel: String
    let unitPrice: Int
    let oldUnitPrice: Int?
    let quantity: Int
    let selected: Bool
    let inStock: Bool
    let lineTotal: Int
}

struct CartTotalsDTO: Decodable, Hashable {
    let itemsCount: Int
    let subtotal: Int
    let discount: Int
    let deliveryFee: Int
    let total: Int
    let freeDeliveryThreshold: Int
    let promoCode: String?
}

struct CartDTO: Decodable {
    let items: [CartItemDTO]
    let totals: CartTotalsDTO
}

struct CartAddRequest: Encodable {
    let productId: Int
    /// The size. A cart line carries a size *and* a colour.
    let variantId: Int?
    let colorVariantId: Int?
    let quantity: Int
}

struct CartUpdateRequest: Encodable {
    var quantity: Int?
    var selected: Bool?
}

struct PromoRequest: Encodable {
    let code: String
}

// MARK: - Delivery

struct AddressDTO: Decodable, Identifiable, Hashable {
    let id: Int
    let title: String
    let icon: String
    let badge: String?
    let line: String
    let city: String
    let meta: String
    let floor: String?
    let apartment: String?
    let entranceCode: String?
    let comment: String?
    let latitude: Double?
    let longitude: Double?
    let isDefault: Bool
}

struct AddressRequest: Encodable {
    var title: String = L("preset_uy")
    var icon: String = "pin"
    var badge: String?
    var line: String
    var city: String = L("region_toshkent")
    var floor: String?
    var apartment: String?
    var entranceCode: String?
    var comment: String?
    var latitude: Double?
    var longitude: Double?
    var isDefault: Bool = false
}

struct PickupPointDTO: Decodable, Identifiable, Hashable {
    let id: Int
    let name: String
    let address: String
    let hours: String
    let distanceKm: Double?
}

struct SlotDTO: Decodable, Identifiable, Hashable {
    let id: Int
    let day: String
    let startTime: String
    let endTime: String
    let label: String
    let note: String
    let price: Int
    let express: Bool
    let available: Bool
}

struct SlotDayDTO: Decodable, Identifiable, Hashable {
    var id: String { day }
    let day: String
    let weekdayLabel: String
    let dayLabel: String
    let monthLabel: String
    let slots: [SlotDTO]
}

// MARK: - Payment

struct CardDTO: Decodable, Identifiable, Hashable {
    let id: Int
    let brand: String
    let last4: String
    let holder: String
    let expiry: String
    let status: String
    let isDefault: Bool

    var isExpired: Bool { status == "expired" }
}

struct CardRequest: Encodable {
    let brand: String
    let last4: String
    let holder: String
    let expiryMonth: Int
    let expiryYear: Int
    /// The app never sends a card number — only the processor's token.
    let processorToken: String
    let isDefault: Bool
}

// MARK: - Orders

struct OrderItemDTO: Decodable, Identifiable, Hashable {
    let id: Int
    let productId: Int?
    let title: String
    let imageUrl: String
    let variantLabel: String
    let unitPrice: Int
    let quantity: Int
    let lineTotal: Int
    let reviewed: Bool
}

struct OrderEventDTO: Decodable, Hashable, Identifiable {
    var id: String { status + title }
    let status: String
    let title: String
    let happenedAt: String?
    let note: String
    let done: Bool
}

struct OrderSummaryDTO: Decodable, Identifiable, Hashable {
    let id: Int
    let code: String
    let status: String
    let statusLabel: String
    let total: Int
    let itemsCount: Int
    let previewImages: [String]
    let etaLabel: String
    let createdAt: String
    let canCancel: Bool
    let canTrack: Bool
}

struct OrderDTO: Decodable, Identifiable {
    let id: Int
    let code: String
    let status: String
    let statusLabel: String
    let total: Int
    let itemsCount: Int
    let previewImages: [String]
    let etaLabel: String
    let createdAt: String
    let canCancel: Bool
    let canTrack: Bool
    let deliveryKind: String
    let addressLine: String
    let addressMeta: String
    let deliveryDay: String?
    let deliveryStart: String?
    let deliveryEnd: String?
    let paymentMethod: String
    let paymentLabel: String
    let paid: Bool
    let recipientName: String
    let recipientPhone: String
    let subtotal: Int
    let deliveryFee: Int
    let discount: Int
    let items: [OrderItemDTO]
    let events: [OrderEventDTO]
}

struct CheckoutRequest: Encodable {
    var addressId: Int?
    var pickupPointId: Int?
    var slotId: Int?
    var paymentMethod: String = "card"
    var paymentCardId: Int?
    var recipientName: String = ""
    var recipientPhone: String = ""
    var promoCode: String?
    var comment: String = ""
}

struct CheckoutPreviewDTO: Decodable {
    let items: [CartItemDTO]
    let address: AddressDTO?
    let pickupPoint: PickupPointDTO?
    let slot: SlotDTO?
    let card: CardDTO?
    let totals: CartTotalsDTO
}

struct ReasonDTO: Decodable, Identifiable, Hashable {
    let id: Int
    let label: String
    let requiresComment: Bool
}

struct CancelRequest: Encodable {
    var reasonId: Int?
    var reason: String = ""
    var comment: String = ""
}

struct ReturnRequestBody: Encodable {
    var orderItemId: Int?
    var reasonId: Int?
    var reason: String = ""
    var comment: String = ""
    var photos: [String] = []
}

struct ReturnDTO: Decodable, Identifiable {
    let id: Int
    let orderCode: String
    let reason: String
    let comment: String
    let status: String
    let createdAt: String
}

// MARK: - Misc

struct NotificationDTO: Decodable, Identifiable, Hashable {
    let id: Int
    let kind: String
    let icon: String
    let title: String
    let text: String
    let deepLink: String?
    let read: Bool
    let createdAt: String
}

struct NotificationGroupDTO: Decodable, Identifiable {
    var id: String { label }
    let label: String
    let items: [NotificationDTO]
}

struct FaqDTO: Decodable, Identifiable {
    let id: Int
    let question: String
    let answer: String
}

struct LegalDocDTO: Decodable, Identifiable {
    var id: String { slug }
    let slug: String
    let icon: String
    let title: String
    let meta: String
}

struct LegalDocFullDTO: Decodable {
    let slug: String
    let icon: String
    let title: String
    let meta: String
    let body: String
}
