import Foundation
import Observation

/// Screens 36–40.
@Observable
final class SettingsModel {
    var settings: SettingsDTO?
    var prefs: NotificationPrefsDTO?
    var languages: [[String: String]] = []
    var hasPin = false
    var biometrics = false

    private let profile = ProfileRepository()
    private let content = ContentRepository()

    @MainActor
    func load() async {
        settings = (await profile.settings()).value
        prefs = (await profile.notificationPrefs()).value
        if let user = (await profile.me()).value {
            hasPin = user.hasPin
            biometrics = user.biometricsEnabled
        }
        languages = (await content.languages()).value ?? []
    }

    @MainActor func setLanguage(_ code: String) async {
        settings = (await profile.updateSettings(SettingsRequest(language: code))).value ?? settings
    }

    @MainActor func setLocation(_ enabled: Bool) async {
        settings = (await profile.updateSettings(SettingsRequest(locationEnabled: enabled))).value ?? settings
    }

    @MainActor func setNightMode(_ enabled: Bool) async {
        settings = (await profile.updateSettings(SettingsRequest(nightMode: enabled))).value ?? settings
    }

    @MainActor func setBiometrics(_ enabled: Bool) async {
        if let user = (await profile.setBiometrics(enabled)).value {
            biometrics = user.biometricsEnabled
        }
    }

    @MainActor func setPref(_ body: NotificationPrefsRequest) async {
        prefs = (await profile.updateNotificationPrefs(body)).value ?? prefs
    }

    var languageLabel: String {
        switch settings?.language {
        case "ru": return "Русский"
        case "en": return "English"
        default: return "O'zbekcha"
        }
    }
}

/// Screen 36 — Bildirishnomalar.
@Observable
final class NotificationsModel {
    var groups: [NotificationGroupDTO] = []
    private let repo = ProfileRepository()

    @MainActor
    func load() async {
        groups = (await repo.notifications()).value ?? []
    }

    @MainActor
    func markAllRead() async {
        await repo.markNotificationsRead()
        await load()
    }
}

/// Screens 41–44: current code → new code → confirm → success.
@Observable
final class PinModel {
    static let length = 4

    var step = 0
    var current = ""
    var first = ""
    var confirm = ""
    var errorMessage: String?
    var submitting = false
    var done = false

    private let repo = AuthRepository()

    var currentValue: String {
        switch step {
        case 0: return current
        case 1: return first
        default: return confirm
        }
    }

    @MainActor
    func start(hasPin: Bool) {
        step = hasPin ? 0 : 1
        current = ""
        first = ""
        confirm = ""
        errorMessage = nil
        done = false
    }

    @MainActor
    func input(_ value: String) async {
        let digits = String(value.filter(\.isNumber).prefix(Self.length))
        errorMessage = nil
        switch step {
        case 0:
            current = digits
            if digits.count == Self.length { step = 1 }
        case 1:
            first = digits
            if digits.count == Self.length { step = 2 }
        default:
            confirm = digits
            if digits.count == Self.length { await submit() }
        }
    }

    @MainActor
    private func submit() async {
        guard first == confirm else {
            step = 1
            first = ""
            confirm = ""
            errorMessage = L("kodlar_mos_kelmadi")
            return
        }
        submitting = true
        let outcome = await repo.setPin(current: current.isEmpty ? nil : current, new: first)
        submitting = false
        switch outcome {
        case .success:
            done = true
        case .failure(let message):
            step = 0
            current = ""
            first = ""
            confirm = ""
            errorMessage = message
        }
    }
}

/// Screens 45–46.
@Observable
final class ContentModel {
    var faq: [FaqDTO] = []
    var support: [String: String] = [:]
    var docs: [LegalDocDTO] = []
    var doc: LegalDocFullDTO?

    private let repo = ContentRepository()

    @MainActor
    func load() async {
        faq = (await repo.faq()).value ?? []
        support = (await repo.support()).value ?? [:]
        docs = (await repo.legalDocs()).value ?? []
    }

    @MainActor
    func loadDoc(slug: String) async {
        doc = (await repo.legalDoc(slug: slug)).value
    }
}
