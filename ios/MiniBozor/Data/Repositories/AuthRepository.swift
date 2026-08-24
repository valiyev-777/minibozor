import Foundation

/// Screens 05–06 and 41–44.
struct AuthRepository {
    private let api = APIClient.shared

    func requestOtp(phone: String) async -> Outcome<OtpRequestedDTO> {
        await run { try await api.post("auth/otp/request", body: PhoneRequest(phone: phone), authorized: false) }
    }

    /// Stores the token pair and reports whether the account was just created.
    func verifyOtp(phone: String, code: String) async -> Outcome<Bool> {
        do {
            let pair: TokenPairDTO = try await api.post(
                "auth/otp/verify",
                body: OtpVerifyRequest(phone: phone, code: code),
                authorized: false
            )
            await api.store(pair: pair)
            return .success(pair.isNewUser ?? false)
        } catch {
            return .failure(message(from: error))
        }
    }

    /// Signs out locally whatever the server says — a failed revoke must not
    /// leave the user stuck in a session they asked to end.
    func logout() async {
        let _: MessageDTO? = try? await api.post("auth/logout")
        await api.signOutLocally()
    }

    func setPin(current: String?, new: String) async -> Outcome<Void> {
        await run {
            let _: MessageDTO = try await api.post(
                "auth/pin",
                body: PinChangeRequest(currentPin: current, newPin: new)
            )
        }
    }

    func verifyPin(_ pin: String) async -> Outcome<Void> {
        await run {
            let _: MessageDTO = try await api.post("auth/pin/verify", body: PinRequest(pin: pin))
        }
    }
}

// MARK: - Shared plumbing

/// Wraps a throwing call into an `Outcome`, surfacing the backend's own message.
func run<T>(_ block: () async throws -> T) async -> Outcome<T> {
    do {
        return .success(try await block())
    } catch {
        return .failure(message(from: error))
    }
}

func message(from error: Error) -> String {
    (error as? APIError)?.detail ?? error.localizedDescription
}
