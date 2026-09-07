/**
 * Talking to the FastAPI backend.
 *
 * Two rules hold everywhere in here, and both exist because of the browser:
 *
 * - **The access token lives in memory.** Not in `localStorage`, where any
 *   injected script can read it and where it would outlive the tab. It is
 *   short-lived and recovered on load from the refresh cookie instead.
 * - **The refresh token is never touched.** It arrives as an HttpOnly cookie
 *   this code cannot read, so `credentials: "include"` is the whole of our
 *   involvement. The token also comes back in the body of `/auth/verify` for
 *   the mobile apps' sake; we deliberately ignore it.
 */

export const API_URL = import.meta.env["VITE_API_URL"] ?? "http://localhost:8000"
export const BASE = `${API_URL}/api/v1`

let accessToken: string | null = null
let onSignedOut: (() => void) | null = null

export function setAccessToken(token: string | null): void {
  accessToken = token
}

export function setSignedOutHandler(handler: (() => void) | null): void {
  onSignedOut = handler
}

/** An error the backend explained. `message` is meant to be shown as it is. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message)
    this.name = "ApiError"
  }
}

type FieldError = { loc?: (string | number)[]; msg?: string }

/**
 * The sentence to put in front of the user.
 *
 * The backend answers 403, 409 and 422 with something specific and already
 * translated, so there is no call for a "something went wrong" of our own —
 * that would replace an answer with a shrug. FastAPI's own validation errors
 * arrive as a list rather than a string, so those get assembled here.
 */
function messageFrom(status: number, body: unknown): string {
  const detail = (body as { detail?: unknown } | null)?.detail
  if (typeof detail === "string" && detail.trim()) return detail
  if (Array.isArray(detail)) {
    const parts = (detail as FieldError[])
      .map((e) => {
        const field = e.loc?.filter((p) => p !== "body").join(".")
        return field ? `${field}: ${e.msg ?? ""}` : (e.msg ?? "")
      })
      .filter(Boolean)
    if (parts.length) return parts.join("; ")
  }
  if (status === 0) return "Serverga ulanolmadim. Backend ishlab turganini tekshiring."
  return `So'rov bajarilmadi (${status}).`
}

let refreshing: Promise<boolean> | null = null

/**
 * Swap the refresh cookie for a new access token.
 *
 * Shared, so that a screen firing four requests at once and getting four 401s
 * refreshes once rather than four times — the token rotates on every refresh,
 * so a stampede would invalidate its own retries.
 */
async function refreshAccessToken(): Promise<boolean> {
  if (!refreshing) {
    refreshing = (async () => {
      try {
        const res = await fetch(`${BASE}/auth/refresh`, {
          method: "POST",
          credentials: "include",
          headers: { "Accept-Language": "uz" },
        })
        if (!res.ok) return false
        const pair = (await res.json()) as { access_token?: string }
        if (!pair.access_token) return false
        accessToken = pair.access_token
        return true
      } catch {
        return false
      }
    })()
  }
  const ok = await refreshing
  refreshing = null
  return ok
}

export type Query = Record<string, string | number | boolean | null | undefined>

type Options = {
  method?: string
  json?: unknown
  /**
   * A file upload. Sent instead of `json`, and deliberately without a
   * Content-Type of our own: multipart needs a boundary in that header, and
   * the browser is the only thing that knows what boundary it wrote.
   */
  form?: FormData
  query?: Query
  /** Set on the auth calls themselves, which must not try to refresh. */
  noRefresh?: boolean
}

function url(path: string, query?: Query): string {
  const target = new URL(BASE + path)
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== null && value !== undefined && value !== "") {
      target.searchParams.set(key, String(value))
    }
  }
  return target.toString()
}

function body(options: Options): BodyInit | undefined {
  if (options.form) return options.form
  if (options.json !== undefined) return JSON.stringify(options.json)
  return undefined
}

async function send(path: string, options: Options): Promise<Response> {
  const headers: Record<string, string> = { "Accept-Language": "uz" }
  if (accessToken) headers["Authorization"] = `Bearer ${accessToken}`
  if (options.json !== undefined) headers["Content-Type"] = "application/json"
  const payload = body(options)
  return fetch(url(path, options.query), {
    method: options.method ?? "GET",
    credentials: "include",
    headers,
    ...(payload !== undefined ? { body: payload } : {}),
  })
}

export async function api<T>(path: string, options: Options = {}): Promise<T> {
  let res: Response
  try {
    res = await send(path, options)
  } catch {
    throw new ApiError(0, messageFrom(0, null))
  }

  // One retry, and only for an expired access token. A second 401 after a
  // successful refresh means the session is genuinely over.
  if (res.status === 401 && !options.noRefresh) {
    if (await refreshAccessToken()) {
      try {
        res = await send(path, options)
      } catch {
        throw new ApiError(0, messageFrom(0, null))
      }
    }
    if (res.status === 401) {
      accessToken = null
      onSignedOut?.()
    }
  }

  if (res.status === 204) return undefined as T
  const text = await res.text()
  const body: unknown = text ? JSON.parse(text) : null
  if (!res.ok) throw new ApiError(res.status, messageFrom(res.status, body))
  return body as T
}

/** Recover a session on page load, from the cookie alone. */
export async function resumeSession(): Promise<boolean> {
  return refreshAccessToken()
}

/**
 * Upload one file and get back where it landed.
 *
 * Goes through `api` so it inherits the bearer token and the one-retry
 * refresh: a photograph chosen after the access token expired should upload,
 * not fail and lose the file the person picked.
 */
export async function upload<T>(path: string, file: File): Promise<T> {
  const form = new FormData()
  form.append("file", file)
  return api<T>(path, { method: "POST", form })
}
