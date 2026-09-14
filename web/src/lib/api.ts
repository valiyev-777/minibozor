/**
 * The one place this app talks to the API.
 *
 * Three things live here and nowhere else.
 *
 * **The base URL comes from the environment.** `VITE_API_URL`, never a
 * hostname in a component. The API runs on a laptop, on a phone's wifi, and
 * on a server, and a compiled-in host is a rebuild each time it moves.
 *
 * **The access token is refreshed once, not per request.** A 401 pauses the
 * request that hit it, refreshes, and retries — and every other request that
 * arrives while that is in flight waits on the same promise rather than
 * starting its own refresh. Two tabs' worth of parallel queries would
 * otherwise spend a rotation each and race each other into a signed-out state.
 *
 * **An error is a sentence somebody can read.** FastAPI answers with
 * `{"detail": "..."}` and the detail is already translated by `app.i18n` into
 * the language this app asked for, so it is shown as it arrives rather than
 * being replaced by "Something went wrong".
 */

const BASE = (import.meta.env.VITE_API_URL ?? "http://localhost:8000") + "/api/v1"

const ACCESS = "mb.access"
const REFRESH = "mb.refresh"

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export const tokens = {
  access: () => localStorage.getItem(ACCESS),
  refresh: () => localStorage.getItem(REFRESH),
  set(access: string, refresh: string) {
    localStorage.setItem(ACCESS, access)
    localStorage.setItem(REFRESH, refresh)
  },
  clear() {
    localStorage.removeItem(ACCESS)
    localStorage.removeItem(REFRESH)
  },
}

type Options = {
  method?: string
  body?: unknown
  /** A uuid per queued action. Every mutating warehouse and courier door wants one. */
  idempotencyKey?: string
  /** Skip the token — the login screen has none yet. */
  anonymous?: boolean
  signal?: AbortSignal
}

let refreshing: Promise<boolean> | null = null

export async function api<T>(path: string, options: Options = {}): Promise<T> {
  const response = await send(path, options)

  if (response.status === 401 && !options.anonymous) {
    const renewed = await refreshOnce()
    if (renewed) return unwrap<T>(await send(path, options))
    tokens.clear()
    // The session hook listens for this rather than importing the router: a
    // fetch helper that knows about routes is a fetch helper nobody can test.
    window.dispatchEvent(new Event("mb:signed-out"))
  }

  return unwrap<T>(response)
}

async function send(path: string, options: Options): Promise<Response> {
  const headers: Record<string, string> = {
    "Accept-Language": "uz",
  }
  if (options.body !== undefined) headers["Content-Type"] = "application/json"
  if (options.idempotencyKey) headers["Idempotency-Key"] = options.idempotencyKey
  if (!options.anonymous) {
    const access = tokens.access()
    if (access) headers.Authorization = `Bearer ${access}`
  }

  return fetch(BASE + path, {
    method: options.method ?? (options.body === undefined ? "GET" : "POST"),
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
    signal: options.signal,
  })
}

async function unwrap<T>(response: Response): Promise<T> {
  if (response.status === 204) return undefined as T

  const text = await response.text()
  const body = text ? safelyParse(text) : null

  if (!response.ok) {
    throw new ApiError(response.status, detail(body) || response.statusText)
  }
  return body as T
}

/** The field names a person would recognise, for the sentence above. */
const FIELDS: Record<string, string> = {
  name: "nomi",
  title: "nomi",
  phone: "telefon",
  price: "narx",
  quantity: "soni",
  unit_cost: "tannarx",
  colour: "rang",
  size: "o'lcham",
  sku: "kod",
  code: "kod",
  location_code: "yacheyka",
  reason: "sabab",
  note: "izoh",
  slug: "manzil",
  sizes: "o'lchamlar",
  full_name: "ism",
}

function detail(body: unknown): string {
  if (body && typeof body === "object" && "detail" in body) {
    const value = (body as { detail: unknown }).detail
    if (typeof value === "string") return value
    // A validation error is a list of field problems. The first one is the
    // one somebody can act on; the rest are the same form, further down.
    //
    // **Said in Uzbek, and about the field.** FastAPI's own message is
    // Pydantic's English — "String should have at least 1 character" — which
    // is a sentence about a type, shown to a warehouse worker who typed a
    // name wrong. Everything else this API refuses with is already
    // translated by `app.i18n`; this was the one door that let English out.
    if (Array.isArray(value) && value.length) {
      const first = value[0] as { msg?: string; type?: string; loc?: unknown[] }
      const field = Array.isArray(first.loc) ? String(first.loc.at(-1) ?? "") : ""
      const named = FIELDS[field] ?? field
      const about = named ? ` — ${named}` : ""
      if (first.type?.includes("missing")) return `To'ldirilmagan${about}`
      if (first.type?.includes("too_short") || first.type?.includes("min_length")) {
        return `Juda qisqa${about}`
      }
      if (first.type?.includes("too_long") || first.type?.includes("max_length")) {
        return `Juda uzun${about}`
      }
      if (first.type?.includes("greater_than") || first.type?.includes("less_than")) {
        return `Noto'g'ri son${about}`
      }
      return `Ma'lumot noto'g'ri${about}`
    }
  }
  return ""
}

function safelyParse(text: string): unknown {
  try {
    return JSON.parse(text)
  } catch {
    return { detail: text }
  }
}

async function refreshOnce(): Promise<boolean> {
  const token = tokens.refresh()
  if (!token) return false
  if (refreshing) return refreshing

  refreshing = (async () => {
    try {
      const response = await fetch(`${BASE}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: token }),
      })
      if (!response.ok) return false
      const pair = (await response.json()) as {
        access_token: string
        refresh_token: string
      }
      tokens.set(pair.access_token, pair.refresh_token)
      return true
    } catch {
      return false
    } finally {
      // Cleared in a microtask rather than here, so the callers that arrived
      // while this was in flight all read the same answer.
      queueMicrotask(() => {
        refreshing = null
      })
    }
  })()

  return refreshing
}

/** A fresh key per queued action, so a retry replays instead of repeating. */
export function idempotencyKey(): string {
  return crypto.randomUUID()
}
