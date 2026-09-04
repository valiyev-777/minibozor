import * as React from "react"
import { api, ApiError, resumeSession, setAccessToken, setSignedOutHandler } from "@/api/client"
import type { OtpRequested, StaffMe, TokenPair, UserRole } from "@/api/types"

/**
 * Who this app is for, and the menu decides the rest.
 *
 * One application serving several panels: the sidebar is drawn from the role,
 * so an operator sees the queues, the warehouse sees the shelves, and an admin
 * sees both. Anyone the app is not for is told which role they hold rather
 * than shown an empty screen.
 */
export const PANEL_ROLES: UserRole[] = ["operator", "warehouse", "admin"]

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
   * Fetch the signed-in staff member, and refuse anybody this panel is not for.
   *
   * `/staff/me` lets every staff role through — it is the shared "which
   * backoffice am I" endpoint — so the operator panel checks the role itself
   * and says which role it found. A courier who is quietly shown an empty
   * screen will file a bug; one who is told "this panel is for operators"
   * will not.
   */
  const load = React.useCallback(async () => {
    const user = await api<StaffMe>("/staff/me")
    if (!PANEL_ROLES.includes(user.role)) {
      setAccessToken(null)
      throw new ApiError(
        403,
        "Bu panel operator, ombor va administrator uchun. " +
          `Sizning rolingiz — ${user.role}.`,
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
      // Held in memory only. `pair.refresh_token` is in the body for the mobile
      // apps' sake; the browser's copy is the HttpOnly cookie that came with
      // this response, and we deliberately never read the body's.
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
