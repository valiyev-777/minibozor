/**
 * Talking to the FastAPI backend.
 *
 * A copy of the seller cabinet's client rather than a shared package — the
 * same decision that file records, for the same reason: two applications, two
 * bundles, two deployments, and a workspace to share eighty lines would cost
 * more than it saves. This copy has already diverged in the two ways that
 * matter to a courier.
 *
 * **It has a keyed write.** [postKeyed] sends an already-encoded body with an
 * `Idempotency-Key`. Every write in `/courier/*` requires that header and the
 * queue owns both halves of it; see `offline/outbox.ts`.
 *
 * **It tells "no" apart from "no answer".** A request that never reached the
 * server is an `ApiError` with status 0, and the queue treats it completely
 * differently from a 409: one means try again later, the other means the
 * server understood and refused. In a shop that distinction is a nicety. Here
 * it decides whether a delivery is kept or thrown away.
 *
 * Two rules carried over unchanged, both because of the browser:
 *
 * - **The access token lives in memory.** Not `localStorage`, where an
 *   injected script could read it and where it would outlive the tab.
 * - **The refresh token is never touched.** It arrives as an HttpOnly cookie
 *   this code cannot read, so `credentials: "include"` is the whole of our
 *   involvement. It is also in the body of `/auth/otp/verify` for the mobile
 *   apps' sake; we ignore that copy.
 */

export const API_URL = import.meta.env["VITE_API_URL"] ?? "http://localhost:8000"
export const BASE = `${API_URL}/api/v1`

let accessToken: string | null = null
let onSignedOut: (() => void) | null = null

export function setAccessToken(token: string | null): void {
  accessToken = token
}

export function hasAccessToken(): boolean {
  return accessToken !== null
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

  /**
   * Nothing was decided: the request never left, or the answer never came
   * back. The queue keeps the row and its key, and tries again later.
   */
  get isOffline(): boolean {
    return this.status === 0
  }
}

type FieldError = { loc?: (string | number)[]; msg?: string }

/**
 * The sentence to put in front of the courier.
 *
 * The backend answers 400, 403, 409 and 422 with something specific and
 * already in Uzbek — "Bu sizning yetkazishingiz emas", "Smena ochilmagan".
 * That text goes straight to the screen. There is no "something went wrong"
 * here: a courier being told a shrug at somebody's front door has nothing to
 * act on.
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
  if (status === 0) return "Tarmoq yo'q."
  return `So'rov bajarilmadi (${status}).`
}

/**
 * Why a refresh did not produce a token.
 *
 * "expired" and "offline" look the same to a shop cabinet — both mean show the
 * login screen. Here they could not be more different: a courier whose cookie
 * expired must sign in again, and a courier in a basement must be let into
 * their round and their queue without one.
 */
export type RefreshResult = "ok" | "expired" | "offline"

let refreshing: Promise<RefreshResult> | null = null

/**
 * Swap the refresh cookie for a new access token.
 *
 * Shared, so a screen firing four requests at once and getting four 401s
 * refreshes once rather than four times — the token rotates on every refresh,
 * so a stampede would invalidate its own retries.
 *
 * This matters more here than in a cabinet somebody has open on a desk. A
 * queued delivery may be sent hours after it was recorded, by which time the
 * access token is long expired; without this the first thing a courier coming
 * out of a basement would see is their whole queue failing.
 */
async function refreshAccessToken(): Promise<RefreshResult> {
  if (!refreshing) {
    refreshing = (async () => {
      let res: Response
      try {
        res = await fetch(`${BASE}/auth/refresh`, {
          method: "POST",
          credentials: "include",
          headers: { "Accept-Language": "uz" },
        })
      } catch {
        // The request never left. Says nothing about the session.
        return "offline"
      }
      if (!res.ok) return "expired"
      const pair = (await res.json()) as { access_token?: string }
      if (!pair.access_token) return "expired"
      accessToken = pair.access_token
      return "ok"
    })()
  }
  const result = await refreshing
  refreshing = null
  return result
}

export type Query = Record<string, string | number | boolean | null | undefined>

type Options = {
  method?: string
  json?: unknown
  /** An already-encoded body, sent byte for byte. Used only by the queue. */
  raw?: string
  idempotencyKey?: string
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

async function send(path: string, options: Options): Promise<Response> {
  const headers: Record<string, string> = { "Accept-Language": "uz" }
  if (accessToken) headers["Authorization"] = `Bearer ${accessToken}`
  if (options.json !== undefined || options.raw !== undefined) {
    headers["Content-Type"] = "application/json"
  }
  if (options.idempotencyKey) headers["Idempotency-Key"] = options.idempotencyKey
  const body =
    options.raw !== undefined
      ? options.raw
      : options.json !== undefined
        ? JSON.stringify(options.json)
        : undefined
  return fetch(url(path, options.query), {
    method: options.method ?? "GET",
    credentials: "include",
    headers,
    ...(body !== undefined ? { body } : {}),
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
    if ((await refreshAccessToken()) === "ok") {
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

/**
 * A keyed write: the queue's only way out.
 *
 * `body` is a string and not an object on purpose. It was encoded when the
 * courier acted and stored on disk in that form; re-encoding an object here
 * could produce different bytes on the second attempt — a key order, an
 * omitted default — and the server hashes the body along with the key. A body
 * that differs turns a retry into a 409 and loses the action.
 */
export function postKeyed<T>(path: string, key: string, body: string): Promise<T> {
  return api<T>(path, { method: "POST", raw: body, idempotencyKey: key })
}

/**
 * Recover a session on page load, from the cookie alone.
 *
 * The caller needs the reason, not a boolean — see [RefreshResult].
 */
export async function resumeSession(): Promise<RefreshResult> {
  return refreshAccessToken()
}

/**
 * Upload a doorstep photograph and get back the path to put in the body.
 *
 * Only ever called with a network in hand. A photo taken underground cannot
 * become part of a queued delivery: the body was encoded and keyed when the
 * courier pressed the button, and editing it afterwards to add a media path is
 * exactly the different-body-same-key case the server refuses with a 409. The
 * photo is optional precisely so that this can be true — the name of whoever
 * took the goods is the evidence that always works.
 */
export async function uploadMedia(file: File): Promise<{ media_url: string }> {
  const form = new FormData()
  form.append("file", file)
  const headers: Record<string, string> = { "Accept-Language": "uz" }
  if (accessToken) headers["Authorization"] = `Bearer ${accessToken}`
  // No Content-Type: the browser sets it with the multipart boundary, and
  // setting it by hand produces a body the server cannot parse.
  let res: Response
  try {
    res = await fetch(`${BASE}/staff/media`, {
      method: "POST",
      credentials: "include",
      headers,
      body: form,
    })
  } catch {
    throw new ApiError(0, messageFrom(0, null))
  }
  const text = await res.text()
  const body: unknown = text ? JSON.parse(text) : null
  if (!res.ok) throw new ApiError(res.status, messageFrom(res.status, body))
  return body as { media_url: string }
}
