package uz.minibozor.navigation

/**
 * Every destination in the app, numbered against the design's screens so the two
 * stay traceable.
 */
object Routes {
    const val SPLASH = "splash"
    const val ONBOARDING = "onboarding"                    // 01-04
    const val LOGIN = "login"                              // 05
    const val OTP = "otp/{phone}"                          // 06
    fun otp(phone: String) = "otp/$phone"

    // Bottom tabs
    const val HOME = "home"                                // 07
    const val CATALOG = "catalog"                          // 10
    const val CART = "cart"                                // 17, 18
    const val PROFILE = "profile"                          // 30

    const val SEARCH = "search"                            // 08
    const val LISTING = "listing?category={category}&query={query}&title={title}"  // 09, 12
    fun listing(category: String? = null, query: String? = null, title: String? = null) =
        "listing?category=${category.orEmpty()}&query=${query.orEmpty()}&title=${title.orEmpty()}"

    const val SUBCATEGORY = "subcategory/{slug}"           // 11
    fun subcategory(slug: String) = "subcategory/$slug"

    const val PRODUCT = "product/{id}"                     // 14
    fun product(id: Int) = "product/$id"

    const val REVIEWS = "reviews/{productId}"              // 15
    fun reviews(productId: Int) = "reviews/$productId"

    const val WRITE_REVIEW = "write_review/{productId}?orderItemId={orderItemId}"  // 16
    fun writeReview(productId: Int, orderItemId: Int? = null) =
        "write_review/$productId?orderItemId=${orderItemId ?: -1}"

    // Checkout flow
    const val CHECKOUT = "checkout"                        // 19
    const val ADDRESS_FORM = "address_form?id={id}"        // 20
    fun addressForm(id: Int? = null) = "address_form?id=${id ?: -1}"
    const val DELIVERY_TIME = "delivery_time"              // 21
    const val PAYMENT_METHOD = "payment_method"            // 22
    const val CONFIRM = "confirm"                          // 23
    const val ORDER_PLACED = "order_placed/{orderId}"      // 24
    fun orderPlaced(orderId: Int) = "order_placed/$orderId"

    // Orders
    const val TRACKING = "tracking/{orderId}"              // 25
    fun tracking(orderId: Int) = "tracking/$orderId"
    const val ORDERS = "orders"                            // 26
    const val ORDER_DETAIL = "order/{orderId}"             // 27
    fun orderDetail(orderId: Int) = "order/$orderId"
    const val ORDER_CANCEL = "order_cancel/{orderId}"      // 28
    fun orderCancel(orderId: Int) = "order_cancel/$orderId"
    const val ORDER_RETURN = "order_return/{orderId}"      // 29
    fun orderReturn(orderId: Int) = "order_return/$orderId"

    // Account
    const val PERSONAL = "personal"                        // 31
    const val CARDS = "cards"                              // 32
    const val ADDRESSES = "addresses"                      // 33
    const val MY_REVIEWS = "my_reviews"                    // 34
    const val FAVORITES = "favorites"                      // 35
    const val NOTIFICATIONS = "notifications"              // 36
    const val SETTINGS = "settings"                        // 37
    const val NOTIFICATION_SETTINGS = "notification_settings"  // 38
    const val LANGUAGE = "language"                        // 39
    const val SECURITY = "security"                        // 40
    const val PIN = "pin/{mode}"                           // 41-44
    fun pin(mode: PinMode) = "pin/${mode.name.lowercase()}"
    const val HELP = "help"                                // 45
    const val LEGAL = "legal"                              // 46
    const val LEGAL_DOC = "legal/{slug}"
    fun legalDoc(slug: String) = "legal/$slug"
}

enum class PinMode { CHANGE, CREATE, UNLOCK }

/** Args reused across destinations. */
object Args {
    const val PHONE = "phone"
    const val ID = "id"
    const val SLUG = "slug"
    const val CATEGORY = "category"
    const val QUERY = "query"
    const val TITLE = "title"
    const val PRODUCT_ID = "productId"
    const val ORDER_ID = "orderId"
    const val ORDER_ITEM_ID = "orderItemId"
    const val MODE = "mode"
}
