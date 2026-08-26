import Foundation
import Observation

/// App-wide state: where to start, and whether we are signed in.
@Observable
final class AppSession {
    enum Phase {
        case onboarding
        case signIn
        case shop
    }

    private(set) var phase: Phase
    var city: String

    private let defaults = UserDefaults.standard
    private let onboardingKey = "onboarding_seen"
    private let cityKey = "city"
    private let auth = AuthRepository()

    init() {
        city = defaults.string(forKey: cityKey) ?? L("region_toshkent")
        if !defaults.bool(forKey: onboardingKey) {
            phase = .onboarding
        } else {
            phase = TokenStore.shared.isSignedIn ? .shop : .signIn
        }
    }

    func finishOnboarding() {
        defaults.set(true, forKey: onboardingKey)
        phase = TokenStore.shared.isSignedIn ? .shop : .signIn
    }

    func didSignIn() {
        phase = .shop
    }

    func signOut() async {
        await auth.logout()
        CartRepository.shared.clearLocally()
        // Back to the intro, not the sign-in form: the "seen it" flag is
        // cleared too, so a relaunch would show the intro anyway and the two
        // paths would disagree about what the same account sees.
        defaults.set(false, forKey: onboardingKey)
        phase = .onboarding
    }

    func setCity(_ value: String) {
        city = value
        defaults.set(value, forKey: cityKey)
    }
}
