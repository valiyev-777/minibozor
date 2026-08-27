import Foundation

/// Thin async wrapper over `URLSession`.
///
/// Requests carry the access token automatically; a 401 triggers exactly one
/// refresh (serialised by an actor so concurrent screens do not stampede the
/// endpoint) and the original request is replayed.
actor APIClient {
    static let shared = APIClient()

    private let session: URLSession
    private let tokens = TokenStore.shared
    private var refreshTask: Task<Bool, Never>?

    private let decoder: JSONDecoder = {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return decoder
    }()

    private let encoder: JSONEncoder = {
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        return encoder
    }()

    /// Set when the session cannot be recovered, so the UI can show sign-in.
    private(set) var sessionExpired = false

    init(session: URLSession = .shared) {
        self.session = session
    }

    // MARK: - Public surface

    func get<T: Decodable>(
        _ path: String,
        query: [URLQueryItem] = [],
        authorized: Bool = true
    ) async throws -> T {
        try await send(path, method: "GET", query: query, body: Optional<Empty>.none, authorized: authorized)
    }

    func post<T: Decodable, Body: Encodable>(
        _ path: String,
        body: Body,
        query: [URLQueryItem] = [],
        authorized: Bool = true
    ) async throws -> T {
        try await send(path, method: "POST", query: query, body: body, authorized: authorized)
    }

    func post<T: Decodable>(
        _ path: String,
        query: [URLQueryItem] = [],
        authorized: Bool = true
    ) async throws -> T {
        try await send(path, method: "POST", query: query, body: Optional<Empty>.none, authorized: authorized)
    }

    func patch<T: Decodable, Body: Encodable>(
        _ path: String,
        body: Body,
        authorized: Bool = true
    ) async throws -> T {
        try await send(path, method: "PATCH", query: [], body: body, authorized: authorized)
    }

    func put<T: Decodable, Body: Encodable>(
        _ path: String,
        body: Body,
        query: [URLQueryItem] = [],
        authorized: Bool = true
    ) async throws -> T {
        try await send(path, method: "PUT", query: query, body: body, authorized: authorized)
    }

    func put<T: Decodable>(
        _ path: String,
        query: [URLQueryItem] = [],
        authorized: Bool = true
    ) async throws -> T {
        try await send(path, method: "PUT", query: query, body: Optional<Empty>.none, authorized: authorized)
    }

    func delete<T: Decodable>(
        _ path: String,
        query: [URLQueryItem] = [],
        authorized: Bool = true
    ) async throws -> T {
        try await send(path, method: "DELETE", query: query, body: Optional<Empty>.none, authorized: authorized)
    }

    func delete<T: Decodable, Body: Encodable>(
        _ path: String,
        body: Body,
        authorized: Bool = true
    ) async throws -> T {
        try await send(path, method: "DELETE", query: [], body: body, authorized: authorized)
    }

    func signOutLocally() {
        tokens.clear()
        sessionExpired = true
    }

    func clearExpiryFlag() {
        sessionExpired = false
    }

    func store(pair: TokenPairDTO) {
        tokens.save(access: pair.accessToken, refresh: pair.refreshToken)
        sessionExpired = false
    }

    // MARK: - Internals

    private struct Empty: Codable {}

    private func send<T: Decodable, Body: Encodable>(
        _ path: String,
        method: String,
        query: [URLQueryItem],
        body: Body?,
        authorized: Bool,
        isRetry: Bool = false
    ) async throws -> T {
        let request = try makeRequest(path, method: method, query: query, body: body, authorized: authorized)

        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await session.data(for: request)
        } catch {
            throw APIError.offline
        }

        guard let http = response as? HTTPURLResponse else {
            throw APIError(status: nil, detail: APIError.defaultMessage(for: 0))
        }

        if http.statusCode == 401, authorized, !isRetry {
            if await refreshSession() {
                return try await send(
                    path, method: method, query: query, body: body,
                    authorized: authorized, isRetry: true
                )
            }
            signOutLocally()
            throw APIError(status: 401, detail: APIError.defaultMessage(for: 401))
        }

        guard (200..<300).contains(http.statusCode) else {
            throw APIError.from(status: http.statusCode, body: data)
        }

        if T.self == Empty.self || data.isEmpty {
            return try decoder.decode(T.self, from: Data("{}".utf8))
        }
        do {
            return try decoder.decode(T.self, from: data)
        } catch {
            throw APIError(status: http.statusCode, detail: L("error_unexpected"))
        }
    }

    private func makeRequest<Body: Encodable>(
        _ path: String,
        method: String,
        query: [URLQueryItem],
        body: Body?,
        authorized: Bool
    ) throws -> URLRequest {
        var components = URLComponents(
            url: AppConfig.apiBaseURL.appendingPathComponent(path),
            resolvingAgainstBaseURL: false
        )
        if !query.isEmpty { components?.queryItems = query }
        guard let url = components?.url else {
            throw APIError(status: nil, detail: L("error_generic"))
        }

        var request = URLRequest(url: url)
        request.httpMethod = method
        request.timeoutInterval = 30
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        // Plenty of what the customer reads comes from the server — category
        // names, order statuses, the FAQ — so it has to be told which language
        // to answer in, or the app is translated around Uzbek content.
        request.setValue(Localization.shared.code, forHTTPHeaderField: "Accept-Language")

        if let body {
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.httpBody = try encoder.encode(body)
        }
        if authorized, let token = tokens.accessToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        return request
    }

    /// One refresh at a time; everyone else awaits the same task.
    private func refreshSession() async -> Bool {
        if let existing = refreshTask {
            return await existing.value
        }
        guard let refresh = tokens.refreshToken else { return false }

        let task = Task<Bool, Never> { [session] in
            // Fresh coders: JSONEncoder/JSONDecoder are not Sendable, so the
            // actor's instances must not cross into this detached work.
            let encoder = JSONEncoder()
            encoder.keyEncodingStrategy = .convertToSnakeCase
            let decoder = JSONDecoder()
            decoder.keyDecodingStrategy = .convertFromSnakeCase

            var request = URLRequest(url: AppConfig.apiBaseURL.appendingPathComponent("auth/refresh"))
            request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.httpBody = try? encoder.encode(RefreshRequest(refreshToken: refresh))

            guard let (data, response) = try? await session.data(for: request),
                  let http = response as? HTTPURLResponse,
                  (200..<300).contains(http.statusCode),
                  let pair = try? decoder.decode(TokenPairDTO.self, from: data)
            else { return false }

            TokenStore.shared.save(access: pair.accessToken, refresh: pair.refreshToken)
            return true
        }
        refreshTask = task
        let result = await task.value
        refreshTask = nil
        return result
    }
}
