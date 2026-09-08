/**
 * Talking to the FastAPI backend.
 *
 * A copy of the other two panels' client rather than a shared package, and
 * that is the decision rather than an accident. Three applications, three
 * bundles, three deployments, three origins — a shared module would need a
 * workspace, a build step and a version to keep them in step, which is more
 * machinery than the eighty lines it would save. They are allowed to drift,
 * and this one already has: it carries `Idempotency-Key`, which no screen at
 * a desk needs and every write on a doorstep does.
 *
 * Two rules hold, and both exist because of the browser:
 *
 * - **The access token lives in memory.** Not in `localStorage`, where any
 *   injected script can read it and where it would outlive the tab. It is
 *   short-lived and recovered on load from the refresh cookie instead.
 * - **The refresh token is never touched.** It arrives as an HttpOnly cookie
 *   this code cannot read, so `credentials: "include"` is the whole of our
 *   involvement. It also comes back in the body of `/auth/otp/verify` for the
 *   mobile apps' sake; we deliberately ignore that copy.
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

/**
 * Where a media path actually is.
 *
 * The API answers with a *relative* path — `uploads/abc.webp` — on purpose,
 * and its own comment says why: the server has no idea how a client reaches
 * it. An emulator uses 10.0.2.2, a USB-attached phone its own localhost
 * through `adb reverse`, a simulator localhost, production a CDN. So every
 * client prefixes its own base, and this is ours.
 *
 * Left alone if it is already absolute: some rows hold a full URL, and
 * prefixing one produces a 404 that looks like a missing file.
 */
export function mediaUrl(path: string | null | undefined): string | undefined {
  if (!path) return undefined
  if (path.startsWith("http://") || path.startsWith("https://")) return path
  return `${API_URL}/media/${path.replace(/^\/+/, "")}`
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
 * The sentence to put in front of the courier.
 *
 * The backend answers 403, 409 and 422 with something specific and already
 * translated — "Bu sizning taklifingiz emas" is the whole explanation. There
 * is no "something went wrong" in this codebase; adding one would replace an
 * answer with a shrug, and this is the screen where somebody is looking at
 * their own money.
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
  if (status === 0) return "Serverga ulanolmadim. Internetni tekshirib, qaytadan urinib ko'ring."
  return `So'rov bajarilmadi (${status}).`
}

let refreshing: Promise<boolean> | null = null

/**
 * Swap the refresh cookie for a new access token.
 *
 * Shared, so a screen firing four requests at once and getting four 401s
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
   * A multipart body — a photograph on its way to `POST /staff/media`.
   *
   * Separate from `json` because the two cannot share a header: `fetch`
   * derives `multipart/form-data` *and its boundary* from the FormData
   * itself, and setting Content-Type by hand omits the boundary, which the
   * server then cannot parse. So the rule is that this path sets no
   * Content-Type at all — see `send`.
   */
  form?: FormData
  query?: Query
  /** Set on the auth calls themselves, which must not try to refresh. */
  noRefresh?: boolean
  /**
   * `Idempotency-Key`, required on every `/courier/*` write.
   *
   * Carried here rather than in each caller's headers so that the *retry*
   * inside `api` — the one that follows a token refresh — sends the same key
   * as the attempt that got the 401. A retry with a fresh key is not a retry;
   * it is a second delivery.
   */
  key?: string
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
  if (options.json !== undefined) headers["Content-Type"] = "application/json"
  if (options.key) headers["Idempotency-Key"] = options.key
  // Deliberately no Content-Type for `form`: the boundary comes from the
  // FormData and only `fetch` knows it.
  const body =
    options.form !== undefined
      ? options.form
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

/**
 * Upload one photograph and get back the path the server stored.
 *
 * The evidence a courier leaves at a door: who took the parcel, and a picture
 * if there was signal to send one. Goes through `api` so an expired access
 * token is refreshed and the upload retried rather than losing the photograph
 * to a 401 after an hour on the round.
 *
 * The bytes are not what gets stored: the server decodes, shrinks and
 * re-encodes them, so `media_url` is a picture it produced.
 */
export async function uploadImage(file: File): Promise<MediaUploaded> {
  const form = new FormData()
  form.append("file", file, file.name)
  return api<MediaUploaded>("/staff/media", { method: "POST", form })
}

export type MediaUploaded = {
  media_url: string
  width: number
  height: number
  bytes: number
}

/** Recover a session on page load, from the cookie alone. */
export async function resumeSession(): Promise<boolean> {
  return refreshAccessToken()
}
