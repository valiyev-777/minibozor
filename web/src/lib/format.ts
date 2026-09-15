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

/* The days and the months, written out.
 *
 * Not `Intl.DateTimeFormat("uz-UZ", { weekday: "long" })` — the top of this
 * file is about exactly this: a runtime without the locale data answers in
 * English, silently, and the courier's home screen greets them with
 * "Thursday". Fourteen words is a cheaper guarantee than a polyfill. */
const DAYS = [
  "Yakshanba",
  "Dushanba",
  "Seshanba",
  "Chorshanba",
  "Payshanba",
  "Juma",
  "Shanba",
]

const MONTHS = [
  "yanvar",
  "fevral",
  "mart",
  "aprel",
  "may",
  "iyun",
  "iyul",
  "avgust",
  "sentabr",
  "oktabr",
  "noyabr",
  "dekabr",
]

/** `Payshanba, 15-sentabr` — the line over the courier's day. */
export function dayLine(value: string | Date | null | undefined): string {
  const when = asDate(value)
  if (!when) return ""
  return `${DAYS[when.getDay()]}, ${when.getDate()}-${MONTHS[when.getMonth()]}`
}

/** `15-sentabr`, without the weekday. */
export function dayMonth(value: string | Date | null | undefined): string {
  const when = asDate(value)
  if (!when) return ""
  return `${when.getDate()}-${MONTHS[when.getMonth()]}`
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

/**
 * `17 soat`, `3 kun`, `12 daqiqa` — the same age in one unit.
 *
 * For a row too narrow to hold two. "17 soat 3 daqiqa" in a queue row is
 * three words of precision nobody acts on differently, and it pushed the
 * figure it was explaining off the end of the line.
 */
export function ageBrief(minutes: number): string {
  const total = Math.max(0, Math.round(minutes))
  const days = Math.floor(total / 1440)
  if (days) return `${days} kun`
  const hours = Math.floor(total / 60)
  if (hours) return `${hours} soat`
  return `${total} daqiqa`
}

/** `3 dona` — a count with its unit, which every warehouse screen shows. */
export function units(count: number): string {
  return `${groups(count)} dona`
}

/**
 * `25,4 km` — one decimal, and the decimal is a **comma**.
 *
 * Here for the same reason everything else in this file is: `toLocaleString`
 * would pick the separator off whatever locale data the runtime happens to
 * carry, and a courier reading `25.4` on one phone and `25,4` on the next is
 * reading two different conventions for the same round.
 */
export function distance(value: number): string {
  const tenths = Math.round(Math.abs(value) * 10)
  const sign = value < 0 ? "-" : ""
  return `${sign}${groups(Math.floor(tenths / 10))},${tenths % 10} km`
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

const WORN = ["XXS", "XS", "S", "M", "L", "XL", "XXL", "XXXL", "3XL", "4XL"]

/**
 * One spelling for a size.
 *
 * A letter size is a letter size however it reaches the keyboard: `xl` and
 * `XL` are the same shirt, and left alone they become two chips, two variants
 * and two barcodes. Numbers keep their own shape, because 41,5 is a number.
 */
export function tidySize(size: string): string {
  const clean = size.trim().replace(/\s+/g, " ")
  return /[a-z]/i.test(clean) ? clean.toUpperCase() : clean
}

/**
 * 41 before 42 before 100, and S before M before L.
 *
 * The same order as the server's, so the row of chips and the row of labels
 * that comes back from it read alike.
 */
export function sizeOrder(size: string): [number, number, string] {
  const clean = size.trim()
  const asNumber = Number(clean.replace(",", "."))
  if (clean !== "" && !Number.isNaN(asNumber)) return [0, asNumber, ""]
  const worn = WORN.indexOf(clean.toUpperCase())
  return worn >= 0 ? [1, worn, ""] : [2, 0, clean.toUpperCase()]
}

/** Sorted the way sizes are worn, for a list of size names. */
export function bySize(one: string, two: string): number {
  const left = sizeOrder(one)
  const right = sizeOrder(two)
  for (let at = 0; at < 3; at += 1) {
    if (left[at] < right[at]) return -1
    if (left[at] > right[at]) return 1
  }
  return 0
}
