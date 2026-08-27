import SwiftUI

@main
struct MiniBozorApp: App {
    @State private var session = AppSession()
    @State private var appearance = Appearance()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(session)
                .environment(appearance)
                .environment(Localization.shared)
                .environment(CartRepository.shared)
                // "Tungi rejim" on means dark; off means follow the phone,
                // which is what the settings row promises.
                .preferredColorScheme(appearance.forceDark ? .dark : nil)
                // The language is read at render time, so the tree has to be
                // rebuilt for a switch to land — the same rebuild Android gets
                // from recreating its activities.
                .id(Localization.shared.code)
        }
    }
}

/// Whether the customer has asked for the dark appearance regardless of the
/// phone's own setting.
@Observable
final class Appearance {
    private let key = "night_mode"
    private let defaults = UserDefaults.standard

    var forceDark: Bool {
        didSet { defaults.set(forceDark, forKey: key) }
    }

    init() {
        forceDark = defaults.bool(forKey: key)
    }
}
