import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"
import { API_URL } from "@/api/client"

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs))
}

export function money(amount: number): string {
  return amount.toLocaleString("ru-RU").replace(/,/g, " ")
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
