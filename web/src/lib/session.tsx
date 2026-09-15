/**
 * Who is signed in, and therefore which application this is.
 *
 * There is one login screen and one bundle. What differs between the office,
 * the bench and the van is the navigation, the density and which routes
 * exist — all of it decided by the role on the account, which the server
 * answers with. A role held in the client would be a role somebody can edit
 * in devtools; every screen behind it is guarded on the server as well.
 */

import { createContext, useCallback, useContext, useEffect, useState } from "react"

import { api, tokens } from "@/lib/api"

export type Role = "admin" | "warehouse" | "courier" | "customer"

export type Staff = {
  id: number
  phone: string
  full_name: string
  role: Role
}

type Session = {
  staff: Staff | null
  loading: boolean
  signIn: (phone: string, code: string) => Promise<Staff>
  signOut: () => void
}

const SessionContext = createContext<Session | null>(null)

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [staff, setStaff] = useState<Staff | null>(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    if (!tokens.access()) {
      setStaff(null)
      setLoading(false)
      return
    }
    try {
      setStaff(await api<Staff>("/me/staff"))
    } catch {
      // A customer's own token reaches this endpoint and is refused, which is
      // the right answer: this application is not for them.
      setStaff(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    // The API helper cannot import the router without becoming untestable, so
    // it announces a dead session and this is what listens.
    const signedOut = () => setStaff(null)
    window.addEventListener("mb:signed-out", signedOut)
    return () => window.removeEventListener("mb:signed-out", signedOut)
  }, [])

  const signIn = useCallback(async (phone: string, code: string) => {
    const pair = await api<{ access_token: string; refresh_token: string }>(
      "/auth/otp/verify",
      { body: { phone, code }, anonymous: true },
    )
    tokens.set(pair.access_token, pair.refresh_token)
    const me = await api<Staff>("/me/staff")
    setStaff(me)
    return me
  }, [])

  const signOut = useCallback(() => {
    const refresh = tokens.refresh()
    if (refresh) void api("/auth/logout", { body: { refresh_token: refresh } }).catch(() => {})
    tokens.clear()
    setStaff(null)
  }, [])

  return (
    <SessionContext.Provider value={{ staff, loading, signIn, signOut }}>
      {children}
    </SessionContext.Provider>
  )
}

export function useSession(): Session {
  const value = useContext(SessionContext)
  if (!value) throw new Error("useSession outside a SessionProvider")
  return value
}
