package uz.minibozor.core.util

/**
 * Card schemes the app recognises from the leading digits (the BIN).
 *
 * Detection is only ever used for display — the brand shown on the form and
 * stored alongside the last four digits. Nothing here decides whether a payment
 * succeeds; the processor does that.
 */
enum class CardBrand(val label: String, val length: Int) {
    HUMO("Humo", 16),
    UZCARD("UzCard", 16),
    VISA("Visa", 16),
    MASTERCARD("Mastercard", 16),
    UNKNOWN("Karta", 16);

    companion object {
        fun of(number: String): CardBrand {
            val digits = number.filter(Char::isDigit)
            val two = digits.take(2).toIntOrNull()
            val four = digits.take(4).toIntOrNull()
            return when {
                digits.startsWith("9860") -> HUMO
                digits.startsWith("8600") || digits.startsWith("5614") -> UZCARD
                digits.startsWith("4") -> VISA
                two != null && digits.length >= 2 && two in 51..55 -> MASTERCARD
                four != null && digits.length >= 4 && four in 2221..2720 -> MASTERCARD
                else -> UNKNOWN
            }
        }
    }
}

/**
 * The ISO/IEC 7812 check digit. Humo and UzCard follow the same standard as the
 * international schemes, so this applies to every brand the app accepts and
 * catches a mistyped digit before the request is made.
 */
fun luhnValid(number: String): Boolean {
    val digits = number.filter(Char::isDigit)
    if (digits.length < 2) return false

    var sum = 0
    var doubled = false
    for (index in digits.indices.reversed()) {
        var value = digits[index] - '0'
        if (doubled) {
            value *= 2
            if (value > 9) value -= 9
        }
        sum += value
        doubled = !doubled
    }
    return sum % 10 == 0
}
