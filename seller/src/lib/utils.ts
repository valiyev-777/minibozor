import { API_URL } from "@/api/client"

// One definition, in the shared design system. Re-exported because every
// screen in this app already imports `cn` from here.
export { cn } from "@/ui/cn"

/**
 * A figure in so'm, grouped and never rounded.
 *
 * The API answers with whole so'm and `toLocaleString` on an integer only
 * groups it. This screen is where a seller reads what they earned, so a
 * formatter that quietly dropped the last digits would be a bug nobody could
 * see by looking.
 */
export function money(amount: number): string {
  return amount.toLocaleString("ru-RU").replace(/,/g, " ")
}

/** With the sign written out, for a column that mixes credits and deductions. */
export function signedMoney(amount: number): string {
  const sign = amount < 0 ? "−" : amount > 0 ? "+" : ""
  return `${sign}${money(Math.abs(amount))}`
}

export function when(iso: string | null | undefined): string {
  if (!iso) return "—"
  return new Date(iso).toLocaleString("uz-UZ", {
    day: "2-digit",
    month: "2-digit",
    year: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  })
}

export function day(iso: string | null | undefined): string {
  if (!iso) return "—"
  return new Date(iso).toLocaleDateString("uz-UZ", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  })
}

/**
 * A Date as `YYYY-MM-DD` in the reader's own timezone.
 *
 * Not `toISOString().slice(0, 10)`, which converts to UTC first: east of
 * Greenwich that turns the 1st of the month into the last of the previous one.
 * Tashkent is UTC+5, so it would be wrong every time.
 */
export function isoDay(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0")
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

/**
 * A label from the API, or nothing.
 *
 * Several shapes send an em-dash as their "no value" placeholder — it reads
 * fine on its own, and reads as a dangling mark when joined to something else
 * ("Choynak · —"). So the emptiness is recovered here rather than in five
 * separate template strings.
 */
export function said(text: string | null | undefined): string {
  const trimmed = (text ?? "").trim()
  return trimmed === "—" || trimmed === "-" ? "" : trimmed
}

/** Bits of a label, joined only where there is something to join. */
export function joined(...parts: (string | null | undefined)[]): string {
  return parts.map(said).filter(Boolean).join(" · ")
}

/** A media path from the API as something an `<img>` can load. */
export function mediaSrc(path: string | null | undefined): string | undefined {
  if (!path) return undefined
  if (path.startsWith("http://") || path.startsWith("https://")) return path
  return `${API_URL}/media/${path.replace(/^\/+/, "")}`
}
