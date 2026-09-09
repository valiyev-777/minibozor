/**
 * Money, dates and ages — written by hand, on purpose.
 *
 * `Intl.NumberFormat("uz-UZ")` and `Intl.DateTimeFormat("uz-UZ")` do not fail
 * when the locale data is missing. They fall back, silently, to whatever the
 * runtime has — so the same build prints `1,250,000` on one machine and
 * `1 250 000` on another, and nobody finds out until a shopkeeper is reading a
 * figure with commas in it. A warehouse screen showing 1,250,000 so'm reads as
 * a different number to the person holding the goods.
 *
 * So there is no `Intl` in this file. Every function here is four lines of
 * arithmetic that does the same thing on every machine, and this is the only
 * file in the app allowed to turn a number or a date into text.
 */

const MONTH_DAY_SEPARATOR = "."

/** `1 250 000 so'm`. A non-breaking space between the groups, so a figure never wraps. */
export function money(amount: number): string {
  return `${groups(amount)} so'm`
}

/** The same, without the unit — for a column of figures under one heading. */
export function groups(amount: number): string {
  const sign = amount < 0 ? "-" : ""
  const digits = Math.abs(Math.round(amount)).toString()
  const out: string[] = []
  for (let i = digits.length; i > 0; i -= 3) {
    out.unshift(digits.slice(Math.max(0, i - 3), i))
  }
  return sign + out.join(" ")
}

/** `08.09.2026` — the order the whole country writes a date in. */
export function date(value: string | Date | null | undefined): string {
  const when = asDate(value)
  if (!when) return ""
  return [pad(when.getDate()), pad(when.getMonth() + 1), when.getFullYear()].join(
    MONTH_DAY_SEPARATOR,
  )
}

/** `14:30`. Twenty-four hours, because a delivery window is written that way. */
export function time(value: string | Date | null | undefined): string {
  const when = asDate(value)
  if (!when) return ""
  return `${pad(when.getHours())}:${pad(when.getMinutes())}`
}

/** `08.09.2026 14:30`, for a row that has to say exactly when. */
export function dateTime(value: string | Date | null | undefined): string {
  const when = asDate(value)
  if (!when) return ""
  return `${date(when)} ${time(when)}`
}

/**
 * `2 soat 10 daqiqa` — how long something has been standing.
 *
 * Words rather than a timestamp because that is the question being asked: a
 * sack in the receiving area is a problem in proportion to how long it has
 * been there, and "09:14" makes the reader do the subtraction.
 */
export function age(minutes: number): string {
  const total = Math.max(0, Math.round(minutes))
  const days = Math.floor(total / 1440)
  const hours = Math.floor((total % 1440) / 60)
  const rest = total % 60

  if (days) return hours ? `${days} kun ${hours} soat` : `${days} kun`
  if (hours) return rest ? `${hours} soat ${rest} daqiqa` : `${hours} soat`
  return `${rest} daqiqa`
}

/** `3 dona` — a count with its unit, which every warehouse screen shows. */
export function units(count: number): string {
  return `${groups(count)} dona`
}

/** `42%`, for a fill bar's label. */
export function percent(value: number): string {
  return `${Math.round(value)}%`
}

/**
 * How many minutes ago the server said something happened.
 *
 * Here rather than beside its first caller because the second caller got it
 * wrong: `Date.parse` on a bare `2026-09-09T06:20:00` reads it as local time,
 * so a card written three minutes ago showed as five hours old on a machine
 * five hours off UTC. `asLocal` is the one place that knows the API sends
 * naive UTC.
 */
export function minutesSince(when: string): number {
  const then = asDate(when)
  if (!then) return 0
  return Math.max(0, Math.round((Date.now() - then.getTime()) / 60_000))
}

function asDate(value: string | Date | null | undefined): Date | null {
  if (!value) return null
  const when = value instanceof Date ? value : new Date(asLocal(value))
  return Number.isNaN(when.getTime()) ? null : when
}

/**
 * The API stores naive UTC and sends it without a zone.
 *
 * A bare `2026-09-08T14:30:00` is read by the browser as *local* time, which
 * happens to be right here — the server and the warehouse are in the same
 * room — and would be an hour or five out the moment either moves. Marking it
 * as UTC and letting the browser convert is the honest reading, and it is
 * what makes an age in minutes agree with the clock on the wall.
 */
function asLocal(value: string): string {
  const hasZone = /Z|[+-]\d\d:?\d\d$/.test(value)
  return hasZone || !value.includes("T") ? value : `${value}Z`
}

function pad(value: number): string {
  return value.toString().padStart(2, "0")
}
