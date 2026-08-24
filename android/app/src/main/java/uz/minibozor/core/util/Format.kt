package uz.minibozor.core.util

import java.time.Instant
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.time.temporal.ChronoUnit

private const val NBSP = ' '

private val UZ_MONTHS = listOf(
    "yanvar", "fevral", "mart", "aprel", "may", "iyun",
    "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr",
)

private val UZ_WEEKDAYS = listOf(
    "Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba",
)

/** `1090000` → `1 090 000`, grouped exactly the way the design writes prices. */
fun Int.grouped(): String {
    val digits = kotlin.math.abs(this).toString()
    val sb = StringBuilder()
    for ((index, ch) in digits.withIndex()) {
        if (index > 0 && (digits.length - index) % 3 == 0) sb.append(NBSP)
        sb.append(ch)
    }
    return if (this < 0) "−$sb" else sb.toString()
}

/** `1090000` → `1 090 000 so'm`. */
fun Int.sum(): String = "${grouped()}${NBSP}so'm"

/** `29` → `−29%`, the discount pill. */
fun Int.discountPill(): String = "−$this%"

fun String.toLocalDateTimeOrNull(): LocalDateTime? = runCatching {
    // The API sends naive UTC, so treat a missing offset as UTC rather than local.
    if (endsWith("Z") || contains('+')) {
        LocalDateTime.ofInstant(Instant.parse(this), ZoneId.systemDefault())
    } else {
        LocalDateTime.parse(this)
            .atZone(ZoneId.of("UTC"))
            .withZoneSameInstant(ZoneId.systemDefault())
            .toLocalDateTime()
    }
}.getOrNull()

fun String.toLocalDateOrNull(): LocalDate? = runCatching { LocalDate.parse(this) }.getOrNull()

/** `2026-08-22T19:40` → `22-avgust, 19:40`. */
fun LocalDateTime.uzDateTime(): String =
    "${dayOfMonth}-${UZ_MONTHS[monthValue - 1]}, ${format(DateTimeFormatter.ofPattern("HH:mm"))}"

/** `2026-08-22` → `22-avgust`. */
fun LocalDate.uzDate(): String = "$dayOfMonth-${UZ_MONTHS[monthValue - 1]}"

/** `Bugun` / `Ertaga` / weekday name — the day chips on the delivery screen. */
fun LocalDate.uzDayLabel(today: LocalDate = LocalDate.now()): String = when (this) {
    today -> "Bugun"
    today.plusDays(1) -> "Ertaga"
    else -> UZ_WEEKDAYS[dayOfWeek.value - 1]
}

fun LocalDate.uzMonth(): String = UZ_MONTHS[monthValue - 1]

/** Relative stamp for notifications and reviews: `12:05`, `19-avg`, `4-iyul`. */
fun LocalDateTime.uzRelative(now: LocalDateTime = LocalDateTime.now()): String = when {
    toLocalDate() == now.toLocalDate() -> format(DateTimeFormatter.ofPattern("HH:mm"))
    ChronoUnit.DAYS.between(toLocalDate(), now.toLocalDate()) < 7 ->
        "$dayOfMonth-${UZ_MONTHS[monthValue - 1].take(3)}"
    else -> toLocalDate().uzDate()
}

/** `+998901234567` → `+998 90 123 45 67`. */
fun String.formatPhone(): String {
    val digits = filter { it.isDigit() }.removePrefix("998")
    if (digits.length != 9) return this
    return "+998 ${digits.substring(0, 2)} ${digits.substring(2, 5)} " +
        "${digits.substring(5, 7)} ${digits.substring(7, 9)}"
}

/** Digits only, `998` prefixed — what the API expects. */
fun String.toApiPhone(): String {
    val digits = filter { it.isDigit() }
    return when {
        digits.startsWith("998") && digits.length == 12 -> "+$digits"
        digits.length == 9 -> "+998$digits"
        else -> "+$digits"
    }
}

fun ratingText(rating: Double): String = String.format(java.util.Locale.US, "%.1f", rating)
