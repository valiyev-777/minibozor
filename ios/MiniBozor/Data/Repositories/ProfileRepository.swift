import Foundation

/// Screens 30–31, 34, 36–40.
struct ProfileRepository {
    private let api = APIClient.shared

    func me() async -> Outcome<UserDTO> {
        await run { try await api.get("me") }
    }

    func updateMe(_ body: UserUpdateRequest) async -> Outcome<UserDTO> {
        await run { try await api.patch("me", body: body) }
    }

    func overview() async -> Outcome<ProfileOverviewDTO> {
        await run { try await api.get("me/overview") }
    }

    func settings() async -> Outcome<SettingsDTO> {
        await run { try await api.get("me/settings") }
    }

    func updateSettings(_ body: SettingsRequest) async -> Outcome<SettingsDTO> {
        await run { try await api.put("me/settings", body: body) }
    }

    func notificationPrefs() async -> Outcome<NotificationPrefsDTO> {
        await run { try await api.get("me/notification-prefs") }
    }

    func updateNotificationPrefs(_ body: NotificationPrefsRequest) async -> Outcome<NotificationPrefsDTO> {
        await run { try await api.put("me/notification-prefs", body: body) }
    }

    func setBiometrics(_ enabled: Bool) async -> Outcome<UserDTO> {
        await run {
            try await api.put(
                "me/biometrics",
                query: [URLQueryItem(name: "enabled", value: enabled ? "true" : "false")]
            )
        }
    }

    func notifications() async -> Outcome<[NotificationGroupDTO]> {
        await run { try await api.get("notifications") }
    }

    func unreadCount() async -> Outcome<Int> {
        await run {
            let payload: [String: Int] = try await api.get("notifications/unread-count")
            return payload["count"] ?? 0
        }
    }

    func markNotificationsRead() async {
        let _: MessageDTO? = try? await api.post("notifications/read")
    }

    func deleteNotification(id: Int) async -> Outcome<Void> {
        await run { let _: MessageDTO = try await api.delete("notifications/\(id)") }
    }

    func myReviews(page: Int = 1) async -> Outcome<PageDTO<ReviewDTO>> {
        await run { try await api.get("me/reviews", query: [URLQueryItem(name: "page", value: String(page))]) }
    }

    func deleteReview(id: Int) async -> Outcome<Void> {
        await run { let _: MessageDTO = try await api.delete("me/reviews/\(id)") }
    }

    func pendingReviews() async -> Outcome<[OrderItemDTO]> {
        await run { try await api.get("me/reviews/pending") }
    }
}

/// Screens 39, 45–46.
struct ContentRepository {
    private let api = APIClient.shared

    func faq() async -> Outcome<[FaqDTO]> {
        await run { try await api.get("help/faq", authorized: false) }
    }

    func support() async -> Outcome<[String: String]> {
        await run { try await api.get("help/support", authorized: false) }
    }

    func legalDocs() async -> Outcome<[LegalDocDTO]> {
        await run { try await api.get("legal", authorized: false) }
    }

    func legalDoc(slug: String) async -> Outcome<LegalDocFullDTO> {
        await run { try await api.get("legal/\(slug)", authorized: false) }
    }

    func languages() async -> Outcome<[[String: String]]> {
        await run { try await api.get("languages", authorized: false) }
    }
}
