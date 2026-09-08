import * as React from "react"
import {
  api,
  ApiError,
  resumeSession,
  setAccessToken,
  setSignedOutHandler,
} from "@/api/client"
import type { OtpRequested, Role, StaffMe, TokenPair } from "@/api/types"

/**
 * Three roles behind one login, and the menu is the difference.
 *
 * The seller's cabinet lets exactly one role in and turns everybody else
 * away. This does the opposite: the warehouse, the operator and the admin all
 * work here, and what each of them may open is a property of the *route*
 * rather than of a second application. So the guard here is only "are you
 * staff of one of these three kinds"; which screens exist for you is decided
 * in `nav.ts`, from this role, in one place.
 *
 * A courier is refused, and told why rather than shown an empty menu: their
 * whole job is a list of doors on a phone, and it is a different application
 * on a different port. A seller is refused for the same reason in the other
 * direction.
 *
 * The same OTP flow customers use. One way in, and the role is the only
 * difference — no second password store, no second login screen to drift.
 */
const PANEL_ROLES: readonly Role[] = ["admin", "operator", "warehouse"]

const ELSEWHERE: Partial<Record<Role, string>> = {
  courier: "Bu — backoffice. Kuryer ilovasi boshqa manzilda: :5175.",
  seller: "Bu — backoffice. Sotuvchi kabineti boshqa manzilda: :5174.",
  customer:
    "Bu hisob xodimga bog'lanmagan. Ilova mijozlar uchun; xodim bo'lsangiz, " +
    "administratordan rol so'rang.",
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

  const load = React.useCallback(async () => {
    const user = await api<StaffMe>("/staff/me")
    if (!PANEL_ROLES.includes(user.role)) {
      setAccessToken(null)
      throw new ApiError(
        403,
        ELSEWHERE[user.role] ?? "Bu panel uchun ruxsatingiz yo'q.",
      )
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
      // mobile apps' sake; the browser's copy is the HttpOnly cookie that came
      // with this response, and we never read the body's.
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

/** The signed-in member of staff, for screens behind the guard. */
export function useStaff(): StaffMe {
  const session = useSession()
  if (session.status !== "signed-in") throw new Error("useStaff before sign-in")
  return session.user
}

/** Their role, which is what decides every menu and every guard. */
export function useRole(): Role {
  return useStaff().role
}
