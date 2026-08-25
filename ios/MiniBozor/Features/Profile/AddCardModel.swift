import Foundation
import Observation

/// Screen 32 — "Yangi karta qo'shish".
///
/// The full card number stays in this object and is never sent anywhere: only
/// the brand, the last four digits, the expiry and a token reach the API.
/// `processorTokenPrefix` marks the one line to replace with the payment
/// provider's SDK result before this goes live — the app must never be the
/// thing that holds a PAN.
@Observable
final class AddCardModel {
    static let processorTokenPrefix = "dev_tok_"

    /// Digits only; never leaves the device.
    var number = ""
    /// Digits only, `MMYY`.
    var expiry = ""
    var holder = ""
    var makeDefault = false

    var saving = false
    var errorMessage: String?
    var done = false

    private let orders = OrderRepository()

    var brand: CardBrand { CardBrand.of(number) }
    var numberComplete: Bool { number.count == brand.length }
    var numberValid: Bool { numberComplete && luhnValid(number) }

    var expiryMonth: Int? {
        guard let month = Int(expiry.prefix(2)), (1...12).contains(month) else { return nil }
        return month
    }

    var expiryYear: Int? {
        guard expiry.count == 4, let year = Int(expiry.dropFirst(2)) else { return nil }
        return 2000 + year
    }

    var expiryValid: Bool {
        guard expiry.count == 4, let month = expiryMonth, let year = expiryYear else { return false }
        let now = Calendar.current.dateComponents([.year, .month], from: Date())
        guard let nowYear = now.year, let nowMonth = now.month else { return false }
        return year > nowYear || (year == nowYear && month >= nowMonth)
    }

    var canSave: Bool { numberValid && expiryValid && !saving }

    var numberError: String? {
        numberComplete && !numberValid ? "Karta raqami noto'g'ri" : nil
    }

    // MARK: - Input

    func setNumber(_ raw: String) {
        number = String(raw.filter(\.isNumber).prefix(19))
        errorMessage = nil
    }

    func setExpiry(_ raw: String) {
        expiry = String(raw.filter(\.isNumber).prefix(4))
        errorMessage = nil
    }

    func setHolder(_ raw: String) {
        holder = raw.uppercased()
        errorMessage = nil
    }

    // MARK: - Save

    @MainActor
    func save() async {
        guard canSave else {
            errorMessage = validationMessage
            return
        }
        saving = true
        errorMessage = nil

        let outcome = await orders.addCard(
            CardRequest(
                brand: brand.label,
                last4: String(number.suffix(4)),
                holder: holder.trimmingCharacters(in: .whitespaces),
                expiryMonth: expiryMonth ?? 1,
                expiryYear: expiryYear ?? 2030,
                // Stand-in for the token the processor's SDK returns.
                processorToken: Self.processorTokenPrefix + UUID().uuidString,
                isDefault: makeDefault
            )
        )
        saving = false

        switch outcome {
        case .success:
            number = ""
            done = true
        case .failure(let message):
            errorMessage = message
        }
    }

    private var validationMessage: String {
        if !numberComplete { return "Karta raqamini to'liq kiriting" }
        if !numberValid { return "Karta raqami noto'g'ri" }
        if expiry.count != 4 { return "Amal qilish muddatini kiriting" }
        if expiryMonth == nil { return "Oy 01–12 oralig'ida bo'lishi kerak" }
        return "Kartaning muddati o'tgan"
    }
}
