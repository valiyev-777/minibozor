import Foundation

/// Where the app points. Debug builds talk to the local FastAPI dev server;
/// `localhost` works from the simulator, and a physical device needs the Mac's
/// LAN address here instead.
enum AppConfig {
    #if DEBUG
    static let apiBaseURL = URL(string: "http://localhost:8000/api/v1")!
    static let mediaBaseURL = "http://localhost:8000/media"
    #else
    static let apiBaseURL = URL(string: "https://api.minibozor.uz/api/v1")!
    static let mediaBaseURL = "https://api.minibozor.uz/media"
    #endif

    static func media(_ path: String) -> URL? {
        if path.hasPrefix("http://") || path.hasPrefix("https://") { return URL(string: path) }
        return URL(string: mediaBaseURL + "/" + path.trimmingCharacters(in: CharacterSet(charactersIn: "/")))
    }
}
