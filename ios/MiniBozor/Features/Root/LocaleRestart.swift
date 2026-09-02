import Foundation

/// The screen the customer was on when they changed the app's language.
///
/// Changing the language rebuilds the whole tree — `MiniBozorApp` keys the root
/// on the language code — because half the text on a product page is translated
/// by the server against the language the request asked for, so every screen
/// needs a new model and a new fetch. What it also threw away was the
/// navigation: whoever switched to Russian on the settings screen was returned
/// to the home page, several taps from the switch they had just used, with no
/// way to tell whether it had worked.
///
/// This outlives the tree, because it is neither in it nor in a model. ``arm()``
/// is called at the moment the language changes; the new tree calls
/// ``consume()`` once as it appears, and gets the tab and the stack back exactly
/// once. Kept armed rather than always restoring, so a rebuild for any other
/// reason is left alone. The Android client does the same thing in
/// `LocaleRestart`.
enum LocaleRestart {
    private(set) static var tab: String?
    private(set) static var path: [Route] = []
    private static var armed = false

    /// Where we are, recorded on every change while the app runs.
    static func remember(tab: String, path: [Route]) {
        Self.tab = tab
        Self.path = path
    }

    /// Called as the language changes, before the tree is rebuilt.
    static func arm() {
        armed = true
    }

    /// The tab and stack to return to, once, or nil.
    static func consume() -> (tab: String, path: [Route])? {
        guard armed, let tab else { return nil }
        armed = false
        return (tab, path)
    }
}
