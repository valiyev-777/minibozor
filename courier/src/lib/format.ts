/**
 * `1090000` → `1 090 000`, with the non-breaking thin space the rest of the
 * product uses so a sum never wraps across a line break.
 *
 * Money is in so'm and the numbers are large: a single order can be eight
 * digits, and a day's cash is the sum of a round of them.
 */
const NBSP = " "

export function grouped(value: number): string {
  const digits = Math.abs(Math.round(value)).toString()
  let out = ""
  for (let i = 0; i < digits.length; i++) {
    if (i > 0 && (digits.length - i) % 3 === 0) out += NBSP
    out += digits[i]
  }
  return value < 0 ? `−${out}` : out
}

export function sum(value: number): string {
  return `${grouped(value)}${NBSP}so'm`
}

/** A difference with its sign kept, because the sign is the whole message. */
export function signedSum(value: number): string {
  return value > 0 ? `+${grouped(value)}${NBSP}so'm` : sum(value)
}

/**
 * The API sends naive UTC, so a stamp with no offset is UTC and not local.
 * Reading it as local put every delivery five hours in the future.
 */
export function parseStamp(value: string | null | undefined): Date | null {
  if (!value) return null
  const iso = /[zZ]$|[+-]\d\d:?\d\d$/.test(value) ? value : `${value}Z`
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? null : date
}

const two = (n: number) => n.toString().padStart(2, "0")

export function clock(date: Date): string {
  return `${two(date.getHours())}:${two(date.getMinutes())}`
}

/** `14:05` if it happened today, `06.09 14:05` if it did not. */
export function stamp(value: string | null | undefined, now = new Date()): string {
  const date = parseStamp(value)
  if (!date) return ""
  const sameDay = date.toDateString() === now.toDateString()
  return sameDay ? clock(date) : `${two(date.getDate())}.${two(date.getMonth() + 1)} ${clock(date)}`
}

/** How long a queued action has been waiting, in words a courier can act on. */
export function waited(since: number, now = Date.now()): string {
  const minutes = Math.floor(Math.max(0, now - since) / 60_000)
  if (minutes < 1) return "hozir"
  if (minutes < 60) return `${minutes} daqiqa oldin`
  if (minutes < 60 * 24) return `${Math.floor(minutes / 60)} soat oldin`
  return `${Math.floor(minutes / (60 * 24))} kun oldin`
}

/** `+998901234567` → `+998 90 123 45 67`, which is how it is read aloud. */
export function prettyPhone(value: string): string {
  const digits = value.replace(/\D/g, "").replace(/^998/, "")
  if (digits.length !== 9) return value
  return `+998 ${digits.slice(0, 2)} ${digits.slice(2, 5)} ${digits.slice(5, 7)} ${digits.slice(7, 9)}`
}

/** Digits only, `+998` prefixed — what the API expects. */
export function toApiPhone(value: string): string {
  const digits = value.replace(/\D/g, "")
  if (digits.startsWith("998") && digits.length === 12) return `+${digits}`
  if (digits.length === 9) return `+998${digits}`
  return `+${digits}`
}

export function dayLabel(iso: string | null | undefined, today = new Date()): string {
  if (!iso) return ""
  const parts = iso.split("-").map(Number)
  const [y, m, d] = parts
  if (!y || !m || !d) return iso
  const date = new Date(y, m - 1, d)
  const diff = Math.round((date.getTime() - new Date(today.getFullYear(), today.getMonth(), today.getDate()).getTime()) / 86_400_000)
  if (diff === 0) return "Bugun"
  if (diff === 1) return "Ertaga"
  if (diff === -1) return "Kecha"
  return `${two(d)}.${two(m)}`
}
