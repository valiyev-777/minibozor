import { API_URL } from "@/api/client"

// One definition, in the shared design system. Re-exported because every
// screen in this app already imports `cn` from here.
export { cn } from "@/ui/cn"

export function money(amount: number): string {
  return amount.toLocaleString("ru-RU").replace(/,/g, " ")
}

/**
 * A ledger amount with its sign said out loud.
 *
 * The API answers in whole so'm and nothing here rounds: these are figures
 * somebody is paid, and a formatter that quietly dropped the last two digits
 * would be a bug nobody could see. `toLocaleString` on an integer only groups
 * it.
 *
 * The sign is written rather than left to a minus glyph that reads as a dash
 * at 12px. A deduction and a credit sitting in one column have to be
 * distinguishable at a glance, or the column is a list of numbers instead of
 * an account.
 */
export function signedMoney(amount: number): string {
  const sign = amount < 0 ? "−" : amount > 0 ? "+" : ""
  return `${sign}${money(Math.abs(amount))}`
}

export function when(iso: string | null | undefined): string {
  if (!iso) return "—"
  const d = new Date(iso)
  return d.toLocaleString("uz-UZ", {
    day: "2-digit",
    month: "2-digit",
    year: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  })
}

/**
 * A Date as `YYYY-MM-DD` in the reader's own timezone.
 *
 * Not `toISOString().slice(0, 10)`, which converts to UTC first: east of
 * Greenwich that turns the 1st of September into the 31st of August, so a
 * form defaulting to "this month" would offer a range a day early and land
 * on the previous period. Tashkent is UTC+5, so it is wrong every time.
 */
export function isoDay(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0")
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

export function day(iso: string | null | undefined): string {
  if (!iso) return "—"
  return new Date(iso).toLocaleDateString("uz-UZ", {
    day: "2-digit",
    month: "2-digit",
    year: "2-digit",
  })
}

/**
 * A media path from the API as something an `<img>` can load.
 *
 * The API answers with a path relative to the media root — `products/x.png`,
 * `uploads/<uuid>.webp` — and never a whole URL, because it does not know how
 * a client reaches it: an emulator uses 10.0.2.2, a phone on USB its own
 * localhost, this panel the API's own host. Each client prefixes its own base,
 * and this is ours. An absolute URL is passed through untouched.
 */
export function mediaSrc(path: string | null | undefined): string | undefined {
  if (!path) return undefined
  if (path.startsWith("http://") || path.startsWith("https://")) return path
  return `${API_URL}/media/${path.replace(/^\/+/, "")}`
}
