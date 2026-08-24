import Foundation
import Observation

/// Screens 05–06. One model drives both, so the phone number survives the push.
@Observable
final class AuthModel {
    static let codeLength = 6

    var phoneDigits = ""
    var code = ""
    var sending = false
    var verifying = false
    var errorMessage: String?
    /// Dev builds of the backend echo the SMS code so the flow works offline.
    var devCode: String?
    var secondsLeft = 0
    var codeSent = false
    var signedIn = false
    var isNewUser = false

    var phoneValid: Bool { phoneDigits.count == 9 }
    var codeValid: Bool { code.count == Self.codeLength }
    var canResend: Bool { secondsLeft == 0 }

    private let repo = AuthRepository()
    private var timer: Task<Void, Never>?

    deinit { timer?.cancel() }

    func setPhone(_ raw: String) {
        phoneDigits = String(raw.filter(\.isNumber).prefix(9))
        errorMessage = nil
    }

    func setCode(_ raw: String) {
        code = String(raw.filter(\.isNumber).prefix(Self.codeLength))
        errorMessage = nil
        if code.count == Self.codeLength {
            Task { await verify() }
        }
    }

    @MainActor
    func sendCode() async {
        guard phoneValid, !sending else { return }
        sending = true
        errorMessage = nil

        switch await repo.requestOtp(phone: Format.apiPhone(phoneDigits)) {
        case .success(let response):
            sending = false
            devCode = response.devCode
            code = ""
            codeSent = true
            startTimer(response.resendAfter)
        case .failure(let message):
            sending = false
            errorMessage = message
        }
    }

    @MainActor
    func verify() async {
        guard codeValid, !verifying else { return }
        verifying = true
        errorMessage = nil

        switch await repo.verifyOtp(phone: Format.apiPhone(phoneDigits), code: code) {
        case .success(let isNew):
            verifying = false
            isNewUser = isNew
            signedIn = true
        case .failure(let message):
            verifying = false
            errorMessage = message
            code = ""
        }
    }

    private func startTimer(_ seconds: Int) {
        timer?.cancel()
        timer = Task { @MainActor in
            for remaining in stride(from: seconds, through: 0, by: -1) {
                secondsLeft = remaining
                try? await Task.sleep(for: .seconds(1))
                if Task.isCancelled { return }
            }
        }
    }
}
