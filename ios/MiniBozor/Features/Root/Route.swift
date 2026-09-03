import Foundation
import Observation

/// Every push destination, numbered against the design's screens.
enum Route: Hashable {
    case search                                    // 08
    case listing(category: String?, query: String?, title: String)  // 09, 12
    case subcategory(slug: String)                 // 11
    case product(id: Int)                          // 14
    case reviews(productId: Int)                   // 15
    case writeReview(productId: Int, orderItemId: Int?)  // 16

    case checkout                                  // 19
    case addressForm                               // 20
    case deliveryTime                              // 21
    case paymentMethod                             // 22
    case confirm                                   // 23
    case orderPlaced(orderId: Int)                 // 24

    case orders                                    // 26
    case orderDetail(orderId: Int)                 // 27
    case orderCancel(orderId: Int)                 // 28
    case orderReturn(orderId: Int)                 // 29

    case personal                                  // 31
    case cards                                     // 32
    case addCard
    case addresses                                 // 33
    case myReviews                                 // 34
    /// Every return asked for, where `orderReturn` is the asking.
    case returns
    case favorites                                 // 35
    case notifications                             // 36
    case settings                                  // 37
    case notificationSettings                      // 38
    case language                                  // 39
    case security                                  // 40
    case pin(hasPin: Bool)                         // 41-44
    case help                                      // 45
    case legal                                     // 46
    case legalDoc(slug: String)
}

/// Wraps a navigation path so screens can push without knowing the stack.
@Observable
final class Router {
    var path: [Route] = []

    func push(_ route: Route) {
        path.append(route)
    }

    func pop() {
        if !path.isEmpty { path.removeLast() }
    }

    func popToRoot() {
        path.removeAll()
    }

    /// Drops everything back to the tab root and pushes one destination —
    /// used after placing an order.
    func replace(with route: Route) {
        path = [route]
    }
}


/// Which of the four tabs is showing.
///
/// Held out here rather than as private state on the tab host, so a sheet deep
/// inside one tab can hand the customer to another — the picker's "O'tish"
/// being the reason.
@Observable
final class TabSelection {
    var current = "home"

    func select(_ id: String) {
        current = id
    }
}
