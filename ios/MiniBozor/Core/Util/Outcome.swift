import Foundation

/// What every repository call returns: a value, or a message the UI can show.
enum Outcome<Success> {
    case success(Success)
    case failure(String)

    var value: Success? {
        if case .success(let value) = self { return value }
        return nil
    }

    var errorMessage: String? {
        if case .failure(let message) = self { return message }
        return nil
    }

    func map<T>(_ transform: (Success) -> T) -> Outcome<T> {
        switch self {
        case .success(let value): return .success(transform(value))
        case .failure(let message): return .failure(message)
        }
    }
}

/// The three states every data-backed screen can be in.
enum LoadState<Value> {
    case loading
    case failed(String)
    case ready(Value)

    var value: Value? {
        if case .ready(let value) = self { return value }
        return nil
    }
}

/// Errors the API layer can raise. `detail` carries the backend's own message,
/// which is already in Uzbek, so it is shown as-is.
struct APIError: LocalizedError {
    let status: Int?
    let detail: String

    var errorDescription: String? { detail }

    static func from(status: Int, body: Data) -> APIError {
        struct Envelope: Decodable { let detail: String? }
        let detail = (try? JSONDecoder().decode(Envelope.self, from: body))?.detail
        return APIError(status: status, detail: detail ?? defaultMessage(for: status))
    }

    static func defaultMessage(for status: Int) -> String {
        switch status {
        case 401: return "Sessiya tugadi. Qaytadan kiring."
        case 404: return "Topilmadi"
        case 409: return "Bu amalni bajarib bo'lmaydi"
        case 500...599: return "Server javob bermayapti. Birozdan so'ng urinib ko'ring."
        default: return "Xatolik yuz berdi"
        }
    }

    static let offline = APIError(
        status: nil,
        detail: "Internetga ulanib bo'lmadi. Aloqani tekshiring."
    )
}
