import SwiftUI

/// Chooses onboarding, sign-in or the shop, and hosts the four tabs.
struct RootView: View {
    @Environment(AppSession.self) var session

    var body: some View {
        switch session.phase {
        case .onboarding:
            OnboardingView { session.finishOnboarding() }
        case .signIn:
            SignInFlowView()
        case .shop:
            ShopTabsView()
        }
    }
}

/// The four tab destinations, each with its own navigation stack, under the
/// floating bar from the design.
struct ShopTabsView: View {
    @Environment(CartRepository.self) var cart

    @State var selection = "home"
    /// One draft order shared by the six checkout steps.
    @State var checkout = CheckoutModel()
    @State var homeRouter = Router()
    @State var catalogRouter = Router()
    @State var cartRouter = Router()
    @State var profileRouter = Router()

    private var activeRouter: Router {
        switch selection {
        case "catalog": return catalogRouter
        case "cart": return cartRouter
        case "profile": return profileRouter
        default: return homeRouter
        }
    }

    private var tabs: [MBTabItem] {
        [
            MBTabItem(id: "home", glyph: "home", label: L("tab_home")),
            MBTabItem(id: "catalog", glyph: "grid", label: L("katalog")),
            MBTabItem(id: "cart", glyph: "cart", label: L("savat"), badge: cart.badgeCount),
            MBTabItem(id: "profile", glyph: "user", label: L("tab_profile")),
        ]
    }

    var body: some View {
        ZStack(alignment: .bottom) {
            Group {
                switch selection {
                case "catalog":
                    RouterStack(router: catalogRouter) { CatalogView() }
                case "cart":
                    RouterStack(router: cartRouter) {
                        CartView(onStartShopping: { selection = "home" })
                    }
                case "profile":
                    RouterStack(router: profileRouter) { ProfileView() }
                default:
                    RouterStack(router: homeRouter) { HomeView() }
                }
            }
            // The design only shows the bar on the four roots, so it hides as
            // soon as the active tab pushes a screen.
            if activeRouter.path.isEmpty {
                MBTabBar(tabs: tabs, selection: $selection)
                    .transition(.move(edge: .bottom).combined(with: .opacity))
            }
        }
        .animation(.easeOut(duration: 0.18), value: activeRouter.path.isEmpty)
        .ignoresSafeArea(.keyboard)
        .environment(checkout)
        .task { await cart.refresh() }
    }
}

/// One tab's navigation stack. Each tab keeps its own `Router`, so switching
/// tabs preserves where the user was — the way the design's bar behaves.
struct RouterStack<Root: View>: View {
    @Bindable var router: Router
    @ViewBuilder var root: Root

    var body: some View {
        NavigationStack(path: $router.path) {
            root
                .navigationDestination(for: Route.self) { route in
                    RouteView(route: route)
                }
        }
        .environment(router)
    }
}

/// Maps a `Route` to its screen. Kept in one place so every stack behaves the
/// same wherever a destination is pushed from.
struct RouteView: View {
    let route: Route
    @Environment(Router.self) var router
    @Environment(AppSession.self) var session

    var body: some View {
        switch route {
        case .search:
            SearchView()
        case .listing(let category, let query, let title):
            ListingView(title: title, category: category, query: query)
        case .subcategory(let slug):
            SubcategoryView(slug: slug)
        case .product(let id):
            ProductView(productId: id)
        case .reviews(let productId):
            ReviewsView(productId: productId)
        case .writeReview(let productId, let orderItemId):
            WriteReviewView(productId: productId, orderItemId: orderItemId)

        case .checkout:
            CheckoutView()
        case .addressForm:
            AddressFormView()
        case .deliveryTime:
            DeliveryTimeView()
        case .paymentMethod:
            PaymentMethodView()
        case .confirm:
            ConfirmView()
        case .orderPlaced(let orderId):
            OrderPlacedView(orderId: orderId)

        case .tracking(let orderId):
            OrderDetailView(orderId: orderId, trackingOnly: true)
        case .orders:
            OrdersView()
        case .orderDetail(let orderId):
            OrderDetailView(orderId: orderId, trackingOnly: false)
        case .orderCancel(let orderId):
            ReasonView(orderId: orderId, isReturn: false)
        case .orderReturn(let orderId):
            ReasonView(orderId: orderId, isReturn: true)

        case .personal:
            PersonalView()
        case .cards:
            CardsView()
        case .addCard:
            AddCardView()
        case .addresses:
            AddressesView()
        case .myReviews:
            MyReviewsView()
        case .favorites:
            FavoritesView()
        case .notifications:
            NotificationsView()
        case .settings:
            SettingsView()
        case .notificationSettings:
            NotificationSettingsView()
        case .language:
            LanguageView()
        case .security:
            SecurityView()
        case .pin(let hasPin):
            PinView(hasPin: hasPin)
        case .help:
            HelpView()
        case .legal:
            LegalView()
        case .legalDoc(let slug):
            LegalDocView(slug: slug)
        }
    }
}
