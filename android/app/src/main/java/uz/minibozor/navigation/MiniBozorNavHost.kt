package uz.minibozor.navigation

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavBackStackEntry
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import androidx.navigation.navigation
import uz.minibozor.BuildConfig
import uz.minibozor.core.design.component.MbLoading
import uz.minibozor.ui.auth.AuthViewModel
import uz.minibozor.ui.auth.LoginScreen
import uz.minibozor.ui.auth.OtpScreen
import uz.minibozor.ui.cart.CartScreen
import uz.minibozor.ui.catalog.CatalogScreen
import uz.minibozor.ui.catalog.ListingScreen
import uz.minibozor.ui.catalog.SubcategoryScreen
import uz.minibozor.ui.checkout.AddressFormScreen
import uz.minibozor.ui.checkout.CheckoutScreen
import uz.minibozor.ui.checkout.CheckoutViewModel
import uz.minibozor.ui.checkout.ConfirmScreen
import uz.minibozor.ui.checkout.DeliveryTimeScreen
import uz.minibozor.ui.checkout.OrderPlacedScreen
import uz.minibozor.ui.checkout.PaymentMethodScreen
import uz.minibozor.ui.home.HomeScreen
import uz.minibozor.ui.onboarding.OnboardingScreen
import uz.minibozor.ui.orders.OrderDetailScreen
import uz.minibozor.ui.orders.OrdersScreen
import uz.minibozor.ui.orders.ReasonScreen
import uz.minibozor.ui.product.ProductScreen
import uz.minibozor.ui.product.ReviewsScreen
import uz.minibozor.ui.product.WriteReviewScreen
import uz.minibozor.ui.profile.AddCardScreen
import uz.minibozor.ui.profile.AddressesScreen
import uz.minibozor.ui.profile.CardsScreen
import uz.minibozor.ui.profile.FavoritesScreen
import uz.minibozor.ui.profile.MyReviewsScreen
import uz.minibozor.ui.profile.PersonalScreen
import uz.minibozor.ui.profile.ProfileScreen
import uz.minibozor.ui.search.SearchScreen
import uz.minibozor.ui.settings.ContentViewModel
import uz.minibozor.ui.settings.HelpScreen
import uz.minibozor.ui.settings.LanguageScreen
import uz.minibozor.ui.settings.LegalDocScreen
import uz.minibozor.ui.settings.LegalScreen
import uz.minibozor.ui.settings.NotificationSettingsScreen
import uz.minibozor.ui.settings.NotificationsScreen
import uz.minibozor.ui.settings.PinScreen
import uz.minibozor.ui.settings.SecurityScreen
import uz.minibozor.ui.settings.SettingsScreen
import uz.minibozor.ui.settings.SettingsViewModel

private const val CHECKOUT_GRAPH = "checkout_graph"

/**
 * The whole app graph. The four tab destinations are wrapped in [MainScaffold];
 * everything else is pushed full-screen over them, matching the design where the
 * floating bar only appears on the four roots.
 */
@Composable
fun MiniBozorNavHost(
    navController: NavHostController = rememberNavController(),
    startViewModel: StartViewModel = hiltViewModel(),
) {
    val start by startViewModel.destination.collectAsStateWithLifecycle()
    val backStackEntry by navController.currentBackStackEntryAsState()
    val currentRoute = backStackEntry?.destination?.route

    if (start == null) {
        Box(Modifier.fillMaxSize()) { MbLoading() }
        return
    }

    fun switchTab(route: String) {
        navController.navigate(route) {
            popUpTo(navController.graph.findStartDestination().id) { saveState = true }
            launchSingleTop = true
            restoreState = true
        }
    }

    fun toSignIn() {
        navController.navigate(Routes.LOGIN) {
            popUpTo(0) { inclusive = true }
        }
    }

    NavHost(navController = navController, startDestination = start!!) {

        // ---------------------------------------------------------- 01-06

        composable(Routes.ONBOARDING) {
            OnboardingScreen(
                mediaBase = BuildConfig.MEDIA_BASE_URL,
                onFinished = {
                    startViewModel.markOnboardingSeen()
                    navController.navigate(Routes.LOGIN) {
                        popUpTo(Routes.ONBOARDING) { inclusive = true }
                    }
                },
            )
        }

        composable(Routes.LOGIN) { entry ->
            LoginScreen(
                onCodeSent = { phone -> navController.navigate(Routes.otp(phone)) },
                onOpenTerms = { navController.navigate(Routes.legalDoc("ommaviy-oferta")) },
                viewModel = entry.sharedAuthViewModel(navController),
            )
        }

        composable(
            Routes.OTP,
            arguments = listOf(navArgument(Args.PHONE) { type = NavType.StringType }),
        ) { entry ->
            OtpScreen(
                phoneDigits = entry.arguments?.getString(Args.PHONE).orEmpty(),
                onBack = { navController.popBackStack() },
                onSignedIn = {
                    navController.navigate(Routes.HOME) { popUpTo(0) { inclusive = true } }
                },
                viewModel = entry.sharedAuthViewModel(navController),
            )
        }

        // ---------------------------------------------------------- tabs

        composable(Routes.HOME) {
            MainScaffold(currentRoute, ::switchTab) {
                HomeScreen(
                    onOpenSearch = { navController.navigate(Routes.SEARCH) },
                    onOpenCategory = { slug -> navController.navigate(Routes.subcategory(slug)) },
                    onOpenProduct = { id -> navController.navigate(Routes.product(id)) },
                    onOpenListing = { category, title ->
                        navController.navigate(Routes.listing(category = category, title = title))
                    },
                )
            }
        }

        composable(Routes.CATALOG) {
            MainScaffold(currentRoute, ::switchTab) {
                CatalogScreen(
                    onOpenSearch = { navController.navigate(Routes.SEARCH) },
                    onOpenCategory = { category ->
                        if (category.hasChildren) {
                            navController.navigate(Routes.subcategory(category.slug))
                        } else {
                            navController.navigate(
                                Routes.listing(category = category.slug, title = category.name)
                            )
                        }
                    },
                )
            }
        }

        composable(Routes.CART) {
            MainScaffold(currentRoute, ::switchTab) {
                CartScreen(
                    onCheckout = { navController.navigate(CHECKOUT_GRAPH) },
                    onOpenProduct = { id -> navController.navigate(Routes.product(id)) },
                    onStartShopping = { switchTab(Routes.HOME) },
                )
            }
        }

        composable(Routes.PROFILE) {
            MainScaffold(currentRoute, ::switchTab) {
                ProfileScreen(
                    onNavigate = { route -> navController.navigate(route) },
                    onSignedOut = ::toSignIn,
                )
            }
        }

        // ---------------------------------------------------------- 08-16

        composable(Routes.SEARCH) {
            SearchScreen(
                onBack = { navController.popBackStack() },
                onSubmit = { query -> navController.navigate(Routes.listing(query = query)) },
                onOpenProduct = { id -> navController.navigate(Routes.product(id)) },
            )
        }

        composable(
            Routes.LISTING,
            arguments = listOf(
                navArgument(Args.CATEGORY) { defaultValue = "" },
                navArgument(Args.QUERY) { defaultValue = "" },
                navArgument(Args.TITLE) { defaultValue = "" },
            ),
        ) { entry ->
            ListingScreen(
                title = entry.arguments?.getString(Args.TITLE).orEmpty(),
                category = entry.arguments?.getString(Args.CATEGORY)?.ifBlank { null },
                query = entry.arguments?.getString(Args.QUERY)?.ifBlank { null },
                onBack = { navController.popBackStack() },
                onOpenProduct = { id -> navController.navigate(Routes.product(id)) },
            )
        }

        composable(
            Routes.SUBCATEGORY,
            arguments = listOf(navArgument(Args.SLUG) { type = NavType.StringType }),
        ) { entry ->
            SubcategoryScreen(
                slug = entry.arguments?.getString(Args.SLUG).orEmpty(),
                onBack = { navController.popBackStack() },
                onOpenListing = { slug, title ->
                    navController.navigate(Routes.listing(category = slug, title = title))
                },
            )
        }

        composable(
            Routes.PRODUCT,
            arguments = listOf(navArgument(Args.ID) { type = NavType.IntType }),
        ) { entry ->
            ProductScreen(
                productId = entry.arguments?.getInt(Args.ID) ?: 0,
                onBack = { navController.popBackStack() },
                onOpenReviews = { id -> navController.navigate(Routes.reviews(id)) },
                onOpenProduct = { id -> navController.navigate(Routes.product(id)) },
                onOpenCart = { switchTab(Routes.CART) },
            )
        }

        composable(
            Routes.REVIEWS,
            arguments = listOf(navArgument(Args.PRODUCT_ID) { type = NavType.IntType }),
        ) { entry ->
            val productId = entry.arguments?.getInt(Args.PRODUCT_ID) ?: 0
            ReviewsScreen(
                productId = productId,
                onBack = { navController.popBackStack() },
                onWriteReview = { navController.navigate(Routes.writeReview(productId)) },
            )
        }

        composable(
            Routes.WRITE_REVIEW,
            arguments = listOf(
                navArgument(Args.PRODUCT_ID) { type = NavType.IntType },
                navArgument(Args.ORDER_ITEM_ID) { defaultValue = "-1" },
            ),
        ) { entry ->
            WriteReviewScreen(
                productId = entry.arguments?.getInt(Args.PRODUCT_ID) ?: 0,
                orderItemId = entry.arguments?.getString(Args.ORDER_ITEM_ID)
                    ?.toIntOrNull()?.takeIf { it > 0 },
                onBack = { navController.popBackStack() },
                onDone = { navController.popBackStack() },
            )
        }

        // ---------------------------------------------------------- 19-24

        navigation(startDestination = Routes.CHECKOUT, route = CHECKOUT_GRAPH) {
            composable(Routes.CHECKOUT) { entry ->
                val vm = entry.checkoutViewModel(navController)
                CheckoutScreen(
                    viewModel = vm,
                    onBack = { navController.popBackStack() },
                    onEditAddress = { navController.navigate(Routes.addressForm()) },
                    onEditTime = { navController.navigate(Routes.DELIVERY_TIME) },
                    onEditPayment = { navController.navigate(Routes.PAYMENT_METHOD) },
                    onConfirm = { navController.navigate(Routes.CONFIRM) },
                )
            }

            composable(
                Routes.ADDRESS_FORM,
                arguments = listOf(navArgument(Args.ID) { defaultValue = "-1" }),
            ) { entry ->
                AddressFormScreen(
                    viewModel = entry.checkoutViewModel(navController),
                    onBack = { navController.popBackStack() },
                    onSaved = { navController.popBackStack() },
                )
            }

            composable(Routes.DELIVERY_TIME) { entry ->
                DeliveryTimeScreen(
                    viewModel = entry.checkoutViewModel(navController),
                    onBack = { navController.popBackStack() },
                    onDone = { navController.popBackStack() },
                )
            }

            composable(Routes.PAYMENT_METHOD) { entry ->
                PaymentMethodScreen(
                    viewModel = entry.checkoutViewModel(navController),
                    onBack = { navController.popBackStack() },
                    onAddCard = { navController.navigate("add_card") },
                    onDone = { navController.popBackStack() },
                )
            }

            composable(Routes.CONFIRM) { entry ->
                ConfirmScreen(
                    viewModel = entry.checkoutViewModel(navController),
                    onBack = { navController.popBackStack() },
                    onPlaced = { orderId ->
                        navController.navigate(Routes.orderPlaced(orderId)) {
                            popUpTo(CHECKOUT_GRAPH) { inclusive = true }
                        }
                    },
                )
            }
        }

        composable(
            Routes.ORDER_PLACED,
            arguments = listOf(navArgument(Args.ORDER_ID) { type = NavType.IntType }),
        ) { entry ->
            val orderId = entry.arguments?.getInt(Args.ORDER_ID) ?: 0
            OrderPlacedScreen(
                orderId = orderId,
                onTrack = { id ->
                    navController.navigate(Routes.tracking(id)) {
                        popUpTo(Routes.ORDER_PLACED) { inclusive = true }
                    }
                },
                onGoHome = {
                    navController.navigate(Routes.HOME) { popUpTo(0) { inclusive = true } }
                },
            )
        }

        // ---------------------------------------------------------- 25-29

        composable(
            Routes.TRACKING,
            arguments = listOf(navArgument(Args.ORDER_ID) { type = NavType.IntType }),
        ) { entry ->
            OrderScreenHost(entry, navController, trackingOnly = true)
        }

        composable(Routes.ORDERS) {
            OrdersScreen(
                onBack = { navController.popBackStack() },
                onOpenOrder = { id -> navController.navigate(Routes.orderDetail(id)) },
                onTrack = { id -> navController.navigate(Routes.tracking(id)) },
                onStartShopping = { switchTab(Routes.HOME) },
            )
        }

        composable(
            Routes.ORDER_DETAIL,
            arguments = listOf(navArgument(Args.ORDER_ID) { type = NavType.IntType }),
        ) { entry ->
            OrderScreenHost(entry, navController, trackingOnly = false)
        }

        composable(
            Routes.ORDER_CANCEL,
            arguments = listOf(navArgument(Args.ORDER_ID) { type = NavType.IntType }),
        ) { entry ->
            ReasonScreen(
                orderId = entry.arguments?.getInt(Args.ORDER_ID) ?: 0,
                isReturn = false,
                onBack = { navController.popBackStack() },
                onDone = { navController.popBackStack() },
            )
        }

        composable(
            Routes.ORDER_RETURN,
            arguments = listOf(navArgument(Args.ORDER_ID) { type = NavType.IntType }),
        ) { entry ->
            ReasonScreen(
                orderId = entry.arguments?.getInt(Args.ORDER_ID) ?: 0,
                isReturn = true,
                onBack = { navController.popBackStack() },
                onDone = { navController.popBackStack() },
            )
        }

        // ---------------------------------------------------------- 31-46

        composable(Routes.PERSONAL) {
            PersonalScreen(onBack = { navController.popBackStack() })
        }

        composable(Routes.CARDS) {
            CardsScreen(
                onBack = { navController.popBackStack() },
                onAddCard = { navController.navigate("add_card") },
            )
        }

        composable("add_card") {
            AddCardScreen(
                onBack = { navController.popBackStack() },
                onSaved = { navController.popBackStack() },
            )
        }

        composable(Routes.ADDRESSES) {
            AddressesScreen(
                onBack = { navController.popBackStack() },
                onAddAddress = { navController.navigate(CHECKOUT_GRAPH) },
            )
        }

        composable(Routes.MY_REVIEWS) {
            MyReviewsScreen(
                onBack = { navController.popBackStack() },
                onOpenProduct = { id -> navController.navigate(Routes.product(id)) },
            )
        }

        composable(Routes.FAVORITES) {
            FavoritesScreen(
                onBack = { navController.popBackStack() },
                onOpenProduct = { id -> navController.navigate(Routes.product(id)) },
                onStartShopping = { switchTab(Routes.HOME) },
            )
        }

        composable(Routes.NOTIFICATIONS) {
            NotificationsScreen(
                onBack = { navController.popBackStack() },
                onOpenDeepLink = { link ->
                    link.substringAfterLast('/').toIntOrNull()?.let { id ->
                        navController.navigate(Routes.orderDetail(id))
                    }
                },
            )
        }

        composable(Routes.SETTINGS) {
            SettingsScreen(
                onBack = { navController.popBackStack() },
                onNavigate = { route -> navController.navigate(route) },
            )
        }

        composable(Routes.NOTIFICATION_SETTINGS) {
            NotificationSettingsScreen(onBack = { navController.popBackStack() })
        }

        composable(Routes.LANGUAGE) {
            LanguageScreen(onBack = { navController.popBackStack() })
        }

        composable(Routes.SECURITY) { entry ->
            val settings: SettingsViewModel = hiltViewModel(entry)
            val state by settings.state.collectAsStateWithLifecycle()
            SecurityScreen(
                onBack = { navController.popBackStack() },
                onChangePin = {
                    navController.navigate(
                        Routes.pin(if (state.hasPin) PinMode.CHANGE else PinMode.CREATE)
                    )
                },
                viewModel = settings,
            )
        }

        composable(
            Routes.PIN,
            arguments = listOf(navArgument(Args.MODE) { defaultValue = "change" }),
        ) { entry ->
            PinScreen(
                hasPin = entry.arguments?.getString(Args.MODE) == "change",
                onBack = { navController.popBackStack() },
                onDone = { navController.popBackStack() },
            )
        }

        composable(Routes.HELP) {
            HelpScreen(onBack = { navController.popBackStack() })
        }

        composable(Routes.LEGAL) {
            LegalScreen(
                onBack = { navController.popBackStack() },
                onOpenDoc = { slug -> navController.navigate(Routes.legalDoc(slug)) },
            )
        }

        composable(
            Routes.LEGAL_DOC,
            arguments = listOf(navArgument(Args.SLUG) { type = NavType.StringType }),
        ) { entry ->
            LegalDocScreen(
                slug = entry.arguments?.getString(Args.SLUG).orEmpty(),
                onBack = { navController.popBackStack() },
            )
        }
    }
}

@Composable
private fun OrderScreenHost(
    entry: NavBackStackEntry,
    navController: NavHostController,
    trackingOnly: Boolean,
) {
    val orderId = entry.arguments?.getInt(Args.ORDER_ID) ?: 0
    OrderDetailScreen(
        orderId = orderId,
        trackingOnly = trackingOnly,
        onBack = { navController.popBackStack() },
        onCancel = { id -> navController.navigate(Routes.orderCancel(id)) },
        onReturn = { id -> navController.navigate(Routes.orderReturn(id)) },
        onWriteReview = { productId, orderItemId ->
            navController.navigate(Routes.writeReview(productId, orderItemId))
        },
    )
}

/** Login and OTP edit one draft, so they share a view model. */
@Composable
private fun NavBackStackEntry.sharedAuthViewModel(
    navController: NavHostController,
): AuthViewModel {
    val parent = remember(this) { navController.getBackStackEntry(Routes.LOGIN) }
    return hiltViewModel(parent)
}

/** The six checkout steps share one draft order. */
@Composable
private fun NavBackStackEntry.checkoutViewModel(
    navController: NavHostController,
): CheckoutViewModel {
    val parent = remember(this) { navController.getBackStackEntry(CHECKOUT_GRAPH) }
    return hiltViewModel(parent)
}
