import Foundation

/// Card schemes the app recognises from the leading digits (the BIN).
///
/// Detection is only ever used for display — the brand shown on the form and
/// stored alongside the last four digits. Nothing here decides whether a
/// payment succeeds; the processor does that.
enum CardBrand: String, CaseIterable {
    case humo, uzcard, visa, mastercard, unknown

    var label: String {
        switch self {
        case .humo: return "Humo"
        case .uzcard: return "UzCard"
        case .visa: return "Visa"
        case .mastercard: return "Mastercard"
        case .unknown: return "Karta"
        }
    }

    var length: Int { 16 }

    static func of(_ number: String) -> CardBrand {
        let digits = number.filter(\.isNumber)
        let two = Int(digits.prefix(2))
        let four = Int(digits.prefix(4))

        if digits.hasPrefix("9860") { return .humo }
        if digits.hasPrefix("8600") || digits.hasPrefix("5614") { return .uzcard }
        if digits.hasPrefix("4") { return .visa }
        if digits.count >= 2, let two, (51...55).contains(two) { return .mastercard }
        if digits.count >= 4, let four, (2221...2720).contains(four) { return .mastercard }
        return .unknown
    }
}

/// The ISO/IEC 7812 check digit. Humo and UzCard follow the same standard as
/// the international schemes, so this applies to every brand the app accepts
/// and catches a mistyped digit before the request is made.
func luhnValid(_ number: String) -> Bool {
    let digits = number.filter(\.isNumber)
    guard digits.count >= 2 else { return false }

    var sum = 0
    var doubled = false
    for character in digits.reversed() {
        guard var value = character.wholeNumberValue else { return false }
        if doubled {
            value *= 2
            if value > 9 { value -= 9 }
        }
        sum += value
        doubled.toggle()
    }
    return sum % 10 == 0
}

enum CardFormat {
    /// `8600123456789011` → `8600 1234 5678 9011`.
    static func number(_ digits: String) -> String {
        stride(from: 0, to: digits.count, by: 4)
            .map { offset -> String in
                let start = digits.index(digits.startIndex, offsetBy: offset)
                let end = digits.index(start, offsetBy: min(4, digits.count - offset))
                return String(digits[start..<end])
            }
            .joined(separator: " ")
    }

    /// `0929` → `09/29`.
    static func expiry(_ digits: String) -> String {
        digits.count > 2 ? "\(digits.prefix(2))/\(digits.dropFirst(2))" : digits
    }
}
