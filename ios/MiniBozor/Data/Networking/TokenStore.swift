import Foundation
import Security

/// Token storage in the Keychain.
///
/// The refresh token is long-lived, so it does not belong in `UserDefaults`.
/// `kSecAttrAccessibleAfterFirstUnlock` keeps it readable to background
/// refreshes without exposing it before the device is first unlocked.
final class TokenStore: @unchecked Sendable {
    static let shared = TokenStore()

    private let service = "uz.minibozor.tokens"
    private let accessKey = "access"
    private let refreshKey = "refresh"
    private let lock = NSLock()

    private init() {}

    var accessToken: String? { read(accessKey) }
    var refreshToken: String? { read(refreshKey) }
    var isSignedIn: Bool { accessToken != nil }

    func save(access: String, refresh: String) {
        lock.lock()
        defer { lock.unlock() }
        write(accessKey, access)
        write(refreshKey, refresh)
    }

    func updateAccess(_ token: String) {
        lock.lock()
        defer { lock.unlock() }
        write(accessKey, token)
    }

    func clear() {
        lock.lock()
        defer { lock.unlock() }
        delete(accessKey)
        delete(refreshKey)
    }

    // MARK: - Keychain

    private func query(_ key: String) -> [String: Any] {
        [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: key,
        ]
    }

    private func read(_ key: String) -> String? {
        var q = query(key)
        q[kSecReturnData as String] = true
        q[kSecMatchLimit as String] = kSecMatchLimitOne

        var item: CFTypeRef?
        guard SecItemCopyMatching(q as CFDictionary, &item) == errSecSuccess,
              let data = item as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }

    private func write(_ key: String, _ value: String) {
        let data = Data(value.utf8)
        let q = query(key)
        let attributes: [String: Any] = [
            kSecValueData as String: data,
            kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlock,
        ]
        if SecItemUpdate(q as CFDictionary, attributes as CFDictionary) == errSecItemNotFound {
            var insert = q
            insert.merge(attributes) { _, new in new }
            SecItemAdd(insert as CFDictionary, nil)
        }
    }

    private func delete(_ key: String) {
        SecItemDelete(query(key) as CFDictionary)
    }
}
