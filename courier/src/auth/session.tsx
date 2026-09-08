import * as React from "react"
import {
  api,
  ApiError,
  resumeSession,
  setAccessToken,
  setSignedOutHandler,
} from "@/api/client"
import type { OtpRequested, StaffMe, TokenPair } from "@/api/types"

/**
 * Who this application is for, which is exactly one role.
 *
 * **Couriers only, and deliberately not admins.** Every door in
 * `app.routers.courier` is scoped to the caller's own round, and an admin has
 * none — they would sign in successfully and be handed an empty list, which is
 * the worst of the three outcomes: it looks like nobody has planned the round.
 * An admin watches the rounds from the backoffice, where the audit trail
 * records that they looked.
 *
 * The same OTP flow customers use. One way in, and the role is the only
 * difference — no second password store and no second login screen to drift
 * from the first.
 */
const PANEL_ROLE = "courier"

/**
 * Where everybody else should be, by name.
 *
 * Somebody quietly shown an empty round files a bug about the round; somebody
 * told "this is the courier's app, the backoffice is on 5173" goes to the
 * right place.
 */
const ELSEWHERE: Record<string, string> = {
  admin: "Bu — kuryer ilovasi. Backoffice boshqa manzilda: :5173.",
  operator: "Bu — kuryer ilovasi. Backoffice boshqa manzilda: :5173.",
  warehouse: "Bu — kuryer ilovasi. Backoffice boshqa manzilda: :5173.",
  seller: "Bu — kuryer ilovasi. Sotuvchi kabineti boshqa manzilda: :5174.",
  customer:
    "Bu hisob kuryerga bog'lanmagan. Kuryer bo'lsangiz, administratordan rol so'rang.",
}

type State =
  | { status: "loading" }
  | { status: "anonymous"; reason?: string }
  | { status: "signed-in"; user: StaffMe }

type Session = State & {
  requestCode: (phone: string) => Promise<OtpRequested>
  signIn: (phone: string, code: string) => Promise<void>
  signOut: () => Promise<void>
}

const Context = React.createContext<Session | null>(null)

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = React.useState<State>({ status: "loading" })

  /**
   * Fetch the signed-in person, and refuse anybody this is not for.
   *
   * `/staff/me` lets every staff role through — it is the shared "which panel
   * am I" endpoint — so the check is here, and `ELSEWHERE` says where the
   * caller should have gone instead.
   */
  const load = React.useCallback(async () => {
    const user = await api<StaffMe>("/staff/me")
    if (user.role !== PANEL_ROLE) {
      setAccessToken(null)
      throw new ApiError(403, ELSEWHERE[user.role] ?? "Bu ilova kuryerlar uchun.")
    }
    setState({ status: "signed-in", user })
  }, [])

  React.useEffect(() => {
    let alive = true
    void (async () => {
      // The access token is gone with the page; the refresh cookie is not.
      const resumed = await resumeSession()
      if (!alive) return
      if (!resumed) {
        setState({ status: "anonymous" })
        return
      }
      try {
        await load()
      } catch (error) {
        if (!alive) return
        setState({
          status: "anonymous",
          ...(error instanceof ApiError && error.status === 403
            ? { reason: error.message }
            : {}),
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

  const value: Session = {
    ...state,
    requestCode: (phone) =>
      api<OtpRequested>("/auth/otp/request", {
        method: "POST",
        json: { phone },
        noRefresh: true,
      }),
    signIn: async (phone, code) => {
      const pair = await api<TokenPair>("/auth/otp/verify", {
        method: "POST",
        json: { phone, code },
        noRefresh: true,
      })
      // Held in memory only. `pair.refresh_token` is in the body for the
      // mobile apps' sake; the browser's copy is the HttpOnly cookie that
      // came with this response, and we never read the body's.
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
  }

  return <Context.Provider value={value}>{children}</Context.Provider>
}

export function useSession(): Session {
  const session = React.useContext(Context)
  if (!session) throw new Error("useSession outside SessionProvider")
  return session
}

/** The signed-in courier, for screens that only render behind the guard. */
export function useCourier(): StaffMe {
  const session = useSession()
  if (session.status !== "signed-in") throw new Error("useCourier before sign-in")
  return session.user
}
