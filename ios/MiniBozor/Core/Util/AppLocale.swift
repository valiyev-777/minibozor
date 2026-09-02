import Foundation
import Observation

/// The app's language.
///
/// iOS applies `AppleLanguages` on the next launch, which is no use for a
/// switch the customer expects to see immediately. So the choice is kept here
/// and every string is read from that language's bundle at render time — the
/// same effect Android gets by recreating its activities, without the restart.
@Observable
final class Localization {
    static let shared = Localization()

    static let fallback = "uz"
    static let supported = [fallback, "ru", "en"]

    private let key = "mb.language"
    private let defaults = UserDefaults.standard

    /// The language in force. An explicit choice on screen 39 wins; failing
    /// that it is the first language iOS knows about that the app speaks, so a
    /// phone set to Russian gets Russian without anyone choosing it.
    private(set) var code: String

    private init() {
        if let chosen = defaults.string(forKey: key), Self.supported.contains(chosen) {
            code = chosen
        } else {
            code = Self.resolvedFromSystem()
        }
    }

    private static func resolvedFromSystem() -> String {
        for tag in Locale.preferredLanguages {
            let language = String(tag.prefix(2))
            if supported.contains(language) { return language }
        }
        return fallback
    }

    func apply(_ value: String) {
        let next = Self.supported.contains(value) ? value : Self.fallback
        guard next != code else { return }
        // The tree below is about to be discarded, navigation and all. This is
        // what lets the screen the switch was made on come back.
        LocaleRestart.arm()
        defaults.set(next, forKey: key)
        // Also told to the system, so the language shows up in Settings for the
        // app and survives a cold start before this object is built.
        defaults.set([next], forKey: "AppleLanguages")
        code = next
    }

    /// The bundle strings are read from. Falls back to the main bundle, which
    /// leaves the base language rather than the key.
    var bundle: Bundle {
        guard
            let path = Bundle.main.path(forResource: code, ofType: "lproj"),
            let localized = Bundle(path: path)
        else { return .main }
        return localized
    }
}

/// A localised string.
///
/// Reads through `Localization.shared` rather than `NSLocalizedString` so a
/// language change takes effect without relaunching.
func L(_ key: String) -> String {
    Localization.shared.bundle.localizedString(forKey: key, value: nil, table: nil)
}

/// A localised string with values in it.
func L(_ key: String, _ arguments: CVarArg...) -> String {
    String(format: L(key), arguments: arguments)
}

/// A counted noun: `count` picks the plural case, `value` is what gets printed.
///
/// Two arguments, not one, because the number on screen is grouped —
/// "2 140 tovar" — while the case has to be chosen from the number itself.
func LPlural(_ key: String, count: Int, _ value: String) -> String {
    String.localizedStringWithFormat(
        Localization.shared.bundle.localizedString(forKey: key, value: nil, table: nil),
        count,
        value
    )
}

/// One entry of a localised list, stored as `name.0`, `name.1`, … because
/// `.strings` has no list type.
func LArray(_ key: String, _ index: Int) -> String {
    L("\(key).\(index)")
}
