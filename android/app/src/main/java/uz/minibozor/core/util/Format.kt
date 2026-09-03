package uz.minibozor.core.util

import java.time.Instant
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.time.Month
import java.time.format.TextStyle
import java.time.temporal.ChronoUnit
import java.util.Locale
import uz.minibozor.R

private const val NBSP = ' '

/**
 * Month and weekday names come from the JDK's own locale data rather than a
 * hand-written table: it already knows "avgust", "августа" and "August", and
 * gets the Russian genitive right, which a table of nominative names would not.
 */
private fun locale(): Locale = Locale.forLanguageTag(AppLocale.current())

private fun monthName(monthValue: Int): String =
    Month.of(monthValue).getDisplayName(TextStyle.FULL, locale())

private fun weekdayName(isoDay: Int): String =
    java.time.DayOfWeek.of(isoDay)
        .getDisplayName(TextStyle.FULL_STANDALONE, locale())
        .replaceFirstChar { it.titlecase(locale()) }

/**
 * `1090000` → `1 090 000`, grouped exactly the way the design writes prices.
 *
 * Long, not Int. Prices here are in so'm, where a wristwatch is 168 000 000 of
 * them — so a basket needed only thirteen of one before the line total passed
 * what a 32-bit Int can hold, and the response stopped being readable at all:
 * "Failed to parse int for input '2688000000'".
 */
fun Long.grouped(): String {
    val digits = kotlin.math.abs(this).toString()
    val sb = StringBuilder()
    for ((index, ch) in digits.withIndex()) {
        if (index > 0 && (digits.length - index) % 3 == 0) sb.append(NBSP)
        sb.append(ch)
    }
    return if (this < 0) "−$sb" else sb.toString()
}

/** For the call sites that hold a count rather than a sum of money. */
fun Int.grouped(): String = toLong().grouped()

/** `1090000` → `1 090 000 so'm`. */
fun Long.sum(): String = "${grouped()}$NBSP${AppStrings[R.string.currency_sum]}"

fun Int.sum(): String = toLong().sum()

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
fun LocalDateTime.uzDateTime(): String = AppStrings[
    R.string.date_day_month_time,
    dayOfMonth,
    monthName(monthValue),
    format(DateTimeFormatter.ofPattern("HH:mm")),
]

/** `2026-08-22` → `22-avgust`. */
fun LocalDate.uzDate(): String =
    AppStrings[R.string.date_day_month, dayOfMonth, monthName(monthValue)]

/** `Bugun` / `Ertaga` / weekday name — the day chips on the delivery screen. */
fun LocalDate.uzDayLabel(today: LocalDate = LocalDate.now()): String = when (this) {
    today -> AppStrings[R.string.bugun]
    today.plusDays(1) -> AppStrings[R.string.ertaga]
    else -> weekdayName(dayOfWeek.value)
}

fun LocalDate.uzMonth(): String = monthName(monthValue)

/** Relative stamp for notifications and reviews: `12:05`, `19-avg`, `4-iyul`. */
fun LocalDateTime.uzRelative(now: LocalDateTime = LocalDateTime.now()): String = when {
    toLocalDate() == now.toLocalDate() -> format(DateTimeFormatter.ofPattern("HH:mm"))
    ChronoUnit.DAYS.between(toLocalDate(), now.toLocalDate()) < 7 ->
        AppStrings[R.string.date_day_month, dayOfMonth, monthName(monthValue).take(3)]
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
