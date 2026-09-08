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
 * The backoffice lets three roles in and draws its menu from whichever one
 * signed in. This does the opposite: **only a seller**, and an admin is
 * turned away as firmly as a customer. That is not tidiness — an admin who
 * could sign in here would be looking at a seller's account through a door
 * built for the seller, with none of the audit trail the backoffice writes
 * when an admin touches somebody's money. They manage sellers from there.
 *
 * The same OTP flow customers use. There is one way in and the role is the
 * only difference, so there is no second password store and no second login
 * screen to drift from the first.
 */
const PANEL_ROLE = "seller"

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
   * am I" endpoint — so the check is here, and it says which role it found.
   * Somebody quietly shown an empty screen files a bug; somebody told "this
   * is the seller's cabinet, you are an admin" goes to the right place.
   */
  const load = React.useCallback(async () => {
    const user = await api<StaffMe>("/staff/me")
    if (user.role !== PANEL_ROLE) {
      setAccessToken(null)
      throw new ApiError(
        403,
        user.role === "admin" || user.role === "operator" || user.role === "warehouse"
          ? `Bu — sotuvchi kabineti. Siz xodimsiz (${user.role}) — backoffice'dan kiring.`
          : "Bu kabinet sotuvchilar uchun. Hisobingiz sotuvchiga bog'lanmagan — " +
            "administratorga murojaat qiling.",
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

/** The signed-in seller, for screens that only render behind the guard. */
export function useSeller(): StaffMe {
  const session = useSession()
  if (session.status !== "signed-in") throw new Error("useSeller before sign-in")
  return session.user
}
