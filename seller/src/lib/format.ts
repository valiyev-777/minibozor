/**
 * Numbers and dates, the way a shopkeeper in Tashkent reads them.
 *
 * One place, because a figure formatted two ways on two screens reads as two
 * different figures. `Intl` rather than hand-rolled grouping: it knows that
 * uz-UZ groups with a space and that a thousand separator is not a comma
 * here.
 */

/**
 * Grouping by hand, and that is deliberate.
 *
 * `Intl.NumberFormat("uz-UZ")` is the obvious answer and it is not
 * dependable: CLDR groups Uzbek with a space, but a browser built with a
 * trimmed ICU falls back to the root locale and produces `215,000` — and it
 * did, in the very Chromium these screens were checked in. A price that
 * groups with a comma on one machine and a space on another is a price two
 * people reading the same screen disagree about, so the separator is ours.
 *
 * A narrow no-break space rather than a plain one: it does not let a figure
 * wrap in the middle, and it is the character CLDR itself specifies.
 */
const GROUP = "\u202f"

function grouped(value: number): string {
  const negative = value < 0
  const digits = Math.round(Math.abs(value)).toString()
  let out = ""
  for (let i = 0; i < digits.length; i++) {
    if (i > 0 && (digits.length - i) % 3 === 0) out += GROUP
    out += digits[i]
  }
  return negative ? `-${out}` : out
}

/**
 * Month names, for the same reason the grouping is ours.
 *
 * `Intl.DateTimeFormat("uz-UZ", { month: "short" })` answered `M09` in the
 * Chromium these screens were checked in — the root-locale fallback, which is
 * a real format and not a bug, and is also not a month anybody in Tashkent
 * reads. Twelve words are cheaper than depending on which ICU a browser was
 * built with.
 */
const MONTHS = [
  "yan", "fev", "mar", "apr", "may", "iyn",
  "iyl", "avg", "sen", "okt", "noy", "dek",
] as const

function pad(value: number): string {
  return value < 10 ? `0${value}` : String(value)
}

/** So'm, grouped, with the unit — the only way prices appear. */
export function som(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—"
  return `${grouped(value)} so'm`
}

/** A bare grouped number, for a count in a column. */
export function num(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—"
  return grouped(value)
}

/** "8 sen 2026" — a day, when the day is all that matters. */
export function date(iso: string | null | undefined): string {
  if (!iso) return "—"
  const at = new Date(iso)
  return `${at.getDate()} ${MONTHS[at.getMonth()]} ${at.getFullYear()}`
}

/**
 * "8 sen 14:32" — a day and a time, without the year.
 *
 * The year is dropped on purpose: everything on these screens happened this
 * month, and a year on every row is four characters of noise in a column that
 * is scanned rather than read.
 */
export function moment(iso: string | null | undefined): string {
  if (!iso) return "—"
  const at = new Date(iso)
  return `${at.getDate()} ${MONTHS[at.getMonth()]} ${pad(at.getHours())}:${pad(at.getMinutes())}`
}

/**
 * "3 kun qoldi", or "muddat o'tdi".
 *
 * A deadline shown as a date makes the reader do the arithmetic, and the
 * whole point of the seller's decision deadline is that they notice it in
 * time. Days rather than hours: the deadline is a week long and an hour's
 * precision would be false.
 */
export function daysLeft(iso: string | null | undefined): number | null {
  if (!iso) return null
  const ms = new Date(iso).getTime() - Date.now()
  return Math.ceil(ms / 86_400_000)
}
