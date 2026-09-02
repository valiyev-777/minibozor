import Foundation

/// Where the app points. Release builds talk to production; debug builds talk to
/// the local FastAPI dev server, where `localhost` works from the simulator.
///
/// Either default can be overridden at build time without editing this file:
/// pass `MB_API_BASE_URL` / `MB_MEDIA_BASE_URL` to xcodebuild and `Info.plist`
/// carries them into the bundle. That is how a TestFlight build gets pointed at
/// a dev machine the phone reaches over Tailscale.
enum AppConfig {
    #if DEBUG
    private static let defaultAPI = "http://localhost:8000/api/v1"
    private static let defaultMedia = "http://localhost:8000/media"
    #else
    private static let defaultAPI = "https://api.minibozor.uz/api/v1"
    private static let defaultMedia = "https://api.minibozor.uz/media"
    #endif

    static let apiBaseURL: URL = {
        if let raw = override("MBAPIBaseURL"), let url = URL(string: raw) { return url }
        return URL(string: defaultAPI)!
    }()

    static let mediaBaseURL = override("MBMediaBaseURL") ?? defaultMedia

    /// An unset build setting expands to an empty string in `Info.plist`, so
    /// blank counts as absent rather than as an override.
    private static func override(_ key: String) -> String? {
        guard let value = Bundle.main.object(forInfoDictionaryKey: key) as? String else { return nil }
        let trimmed = value.trimmingCharacters(in: .whitespaces)
        return trimmed.isEmpty ? nil : trimmed
    }

    static func media(_ path: String) -> URL? {
        if path.hasPrefix("http://") || path.hasPrefix("https://") { return URL(string: path) }
        return URL(string: mediaBaseURL + "/" + path.trimmingCharacters(in: CharacterSet(charactersIn: "/")))
    }
}
