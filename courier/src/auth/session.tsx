import * as React from "react"
import { ApiError, api, resumeSession, setAccessToken, setSignedOutHandler } from "@/api/client"
import type { OtpRequested, StaffMe, TokenPair } from "@/api/types"
import { readCache, writeCache } from "@/offline/cache"

/**
 * Who this application is for, which is exactly one role.
 *
 * A courier, and nobody else. Not an operator, not an admin — and the refusal
 * says which role it found rather than showing an empty screen. Somebody
 * quietly shown nothing files a bug; somebody told "this is the courier app,
 * you are an operator" walks to the right door.
 *
 * `/staff/me` is the endpoint that answers, because the customer profile shape
 * carries no role: two shipped apps read it and it is not going to grow one.
 * Anyone who is not staff at all is refused by that endpoint with a 403, which
 * is a different sentence again — this number is not a member of staff.
 */
const APP_ROLE = "courier"

/**
 * Signed in, but the phone cannot reach the server.
 *
 * A fourth state, and the one this app exists for. A courier who reloads the
 * page in a basement has a valid session they cannot prove: the refresh cookie
 * is there and untouched, but nothing can be asked of it. Sending them to the
 * login screen would put their round and their unsent queue behind an SMS they
 * cannot receive.
 *
 * So the app opens on the identity it last verified, from its own storage, and
 * says it is offline. Nothing is trusted that was not already on this device,
 * no request can succeed without a token anyway, and the moment a network
 * appears the session is properly re-established or properly refused.
 */
type State =
  | { status: "loading" }
  | { status: "anonymous"; reason?: string }
  | { status: "signed-in"; user: StaffMe }
  | { status: "offline"; user: StaffMe }

type Session = State & {
  requestCode: (phone: string) => Promise<OtpRequested>
  signIn: (phone: string, code: string) => Promise<void>
  signOut: () => Promise<void>
  /** Try again to turn an offline session into a verified one. */
  revalidate: () => Promise<void>
}

const Context = React.createContext<Session | null>(null)

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = React.useState<State>({ status: "loading" })

  const load = React.useCallback(async () => {
    const user = await api<StaffMe>("/staff/me")
    if (user.role !== APP_ROLE) {
      setAccessToken(null)
      throw new ApiError(403, refusalFor(user.role))
    }
    // Kept so a reload with no signal knows whose round it is showing. Written
    // only after the role has been checked against a live answer, so an
    // offline start can never let in somebody who was refused.
    await writeCache("identity", user)
    setState({ status: "signed-in", user })
  }, [])

  const revalidate = React.useCallback(async () => {
    const resumed = await resumeSession()
    if (resumed === "ok") {
      try {
        await load()
      } catch (error) {
        setState({
          status: "anonymous",
          ...(error instanceof ApiError && error.status === 403 ? { reason: error.message } : {}),
        })
      }
    }
  }, [load])

  React.useEffect(() => {
    let alive = true
    void (async () => {
      // The access token is gone with the page; the refresh cookie is not.
      const resumed = await resumeSession()
      if (!alive) return

      if (resumed === "offline") {
        const known = await readCache("identity")
        if (!alive) return
        setState(
          known?.data
            ? { status: "offline", user: known.data }
            : // Never signed in on this device, and no way to. There is
              // nothing to show and saying so is the only honest answer.
              { status: "anonymous", reason: "Tarmoq yo'q — kirish uchun internet kerak." },
        )
        return
      }

      if (resumed === "expired") {
        setState({ status: "anonymous" })
        return
      }

      try {
        await load()
      } catch (error) {
        if (!alive) return
        if (error instanceof ApiError && error.isOffline) {
          const known = await readCache("identity")
          setState(
            known?.data
              ? { status: "offline", user: known.data }
              : { status: "anonymous", reason: "Tarmoq yo'q — kirish uchun internet kerak." },
          )
          return
        }
        setState({
          status: "anonymous",
          ...(error instanceof ApiError && error.status === 403 ? { reason: error.message } : {}),
        })
      }
    })()
    return () => {
      alive = false
    }
  }, [load])

  React.useEffect(() => {
    setSignedOutHandler(() => setState({ status: "anonymous" }))
    return () => setSignedOutHandler(null)
  }, [])

  // An offline session becomes a real one as soon as the phone finds signal.
  React.useEffect(() => {
    if (state.status !== "offline") return
    const wake = () => void revalidate()
    window.addEventListener("online", wake)
    const timer = window.setInterval(wake, 20_000)
    return () => {
      window.removeEventListener("online", wake)
      window.clearInterval(timer)
    }
  }, [state.status, revalidate])

  const value: Session = {
    ...state,
    requestCode: (phone) =>
      api<OtpRequested>("/auth/otp/request", { method: "POST", json: { phone }, noRefresh: true }),
    signIn: async (phone, code) => {
      const pair = await api<TokenPair>("/auth/otp/verify", {
        method: "POST",
        json: { phone, code },
        noRefresh: true,
      })
      // Held in memory only. `pair.refresh_token` is in the body for the mobile
      // apps' sake; the browser's copy is the HttpOnly cookie that came with
      // this response, and we never read the body's.
      setAccessToken(pair.access_token)
      await load()
    },
    signOut: async () => {
      try {
        await api("/auth/logout", { method: "POST" })
      } finally {
        setAccessToken(null)
        setState({ status: "anonymous" })
      }
    },
    revalidate,
  }

  return <Context.Provider value={value}>{children}</Context.Provider>
}

/**
 * Why this person is not getting in, in their own terms.
 *
 * Staff who belong somewhere else are pointed at it. Everybody else is told
 * the account is not a courier's and who can change that — an operator, who
 * assigns the role from the backoffice.
 */
function refusalFor(role: string): string {
  const desk: Record<string, string> = {
    admin: "administrator",
    operator: "operator",
    warehouse: "ombor xodimi",
    seller: "sotuvchi",
  }
  const named = desk[role]
  return named
    ? `Bu — kuryer ilovasi. Siz ${named} sifatida kirdingiz, kuryer emas. ` +
        "O'z panelingizdan foydalaning."
    : "Bu ilova kuryerlar uchun. Hisobingizga kuryer roli berilmagan — operatorga murojaat qiling."
}

export function useSession(): Session {
  const session = React.useContext(Context)
  if (!session) throw new Error("useSession outside SessionProvider")
  return session
}

/** The signed-in courier, for screens that only render behind the guard. */
export function useCourier(): StaffMe {
  const session = useSession()
  if (session.status !== "signed-in" && session.status !== "offline") {
    throw new Error("useCourier before sign-in")
  }
  return session.user
}
