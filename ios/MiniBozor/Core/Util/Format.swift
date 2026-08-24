import Foundation

/// Money and date formatting, matching what the design writes on screen.
enum Format {
    /// A narrow non-breaking space, so `1 090 000` never wraps mid-number.
    static let groupSeparator = "\u{202F}"

    /// `1090000` → `1 090 000`.
    static func grouped(_ value: Int) -> String {
        let digits = String(abs(value))
        var out = ""
        for (offset, ch) in digits.enumerated() {
            if offset > 0 && (digits.count - offset) % 3 == 0 { out.append(groupSeparator) }
            out.append(ch)
        }
        return value < 0 ? "−" + out : out
    }

    /// `1090000` → `1 090 000 so'm`.
    static func sum(_ value: Int) -> String {
        grouped(value) + groupSeparator + "so'm"
    }

    static func rating(_ value: Double) -> String {
        String(format: "%.1f", value)
    }

    /// `+998901234567` → `+998 90 123 45 67`.
    static func phone(_ raw: String) -> String {
        var digits = raw.filter(\.isNumber)
        if digits.hasPrefix("998") { digits.removeFirst(3) }
        guard digits.count == 9 else { return raw }
        let d = Array(digits)
        return "+998 \(d[0])\(d[1]) \(d[2])\(d[3])\(d[4]) \(d[5])\(d[6]) \(d[7])\(d[8])"
    }

    /// Digits only, `+998`-prefixed — what the API expects.
    static func apiPhone(_ raw: String) -> String {
        let digits = raw.filter(\.isNumber)
        if digits.count == 12, digits.hasPrefix("998") { return "+" + digits }
        if digits.count == 9 { return "+998" + digits }
        return "+" + digits
    }
}

// MARK: - Uzbek dates

enum UzDate {
    static let months = [
        "yanvar", "fevral", "mart", "aprel", "may", "iyun",
        "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr",
    ]

    static let weekdays = [
        "Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba",
    ]

    private static let calendar = Calendar(identifier: .gregorian)

    /// The API sends naive UTC timestamps; anything without an offset is UTC.
    static func parseDateTime(_ text: String) -> Date? {
        let iso = ISO8601DateFormatter()
        iso.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = iso.date(from: text) { return date }
        iso.formatOptions = [.withInternetDateTime]
        if let date = iso.date(from: text) { return date }

        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone(identifier: "UTC")
        for format in ["yyyy-MM-dd'T'HH:mm:ss.SSSSSS", "yyyy-MM-dd'T'HH:mm:ss", "yyyy-MM-dd'T'HH:mm"] {
            formatter.dateFormat = format
            if let date = formatter.date(from: text) { return date }
        }
        return nil
    }

    static func parseDay(_ text: String) -> Date? {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter.date(from: text)
    }

    /// `22-avgust`.
    static func day(_ date: Date) -> String {
        let parts = calendar.dateComponents([.day, .month], from: date)
        guard let d = parts.day, let m = parts.month else { return "" }
        return "\(d)-\(months[m - 1])"
    }

    /// `22-avgust, 19:40`.
    static func dayTime(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.dateFormat = "HH:mm"
        return "\(day(date)), \(formatter.string(from: date))"
    }

    /// `Bugun` / `Ertaga` / weekday name.
    static func dayLabel(_ date: Date, today: Date = Date()) -> String {
        if calendar.isDate(date, inSameDayAs: today) { return "Bugun" }
        if let tomorrow = calendar.date(byAdding: .day, value: 1, to: today),
           calendar.isDate(date, inSameDayAs: tomorrow) {
            return "Ertaga"
        }
        let weekday = calendar.component(.weekday, from: date)   // 1 = Sunday
        return weekdays[(weekday + 5) % 7]
    }

    /// Relative stamp for notifications and reviews: `12:05`, `19-avg`, `4-iyul`.
    static func relative(_ date: Date, now: Date = Date()) -> String {
        if calendar.isDate(date, inSameDayAs: now) {
            let formatter = DateFormatter()
            formatter.dateFormat = "HH:mm"
            return formatter.string(from: date)
        }
        let days = calendar.dateComponents([.day], from: date, to: now).day ?? 0
        let parts = calendar.dateComponents([.day, .month], from: date)
        guard let d = parts.day, let m = parts.month else { return "" }
        if days < 7 { return "\(d)-\(months[m - 1].prefix(3))" }
        return "\(d)-\(months[m - 1])"
    }
}
