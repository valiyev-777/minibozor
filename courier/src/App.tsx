import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom"
import { Loading } from "@/ui/states"
import { LoginPage } from "@/auth/LoginPage"
import { useSession } from "@/auth/session"
import { Shell } from "@/components/Shell"
import { RoundPage } from "@/pages/RoundPage"
import { StopPage } from "@/pages/StopPage"
import { RunPage } from "@/pages/RunPage"

/**
 * Three screens: the round, one delivery, one collection.
 *
 * Nothing behind the guard is mounted before there is a session, so a screen's
 * query cannot fire while the token is still being recovered from the refresh
 * cookie — on a phone that is the difference between opening the app and
 * seeing the round, and opening it and seeing the login page flash past.
 */
export function App() {
  const session = useSession()

  if (session.status === "loading") {
    return (
      <div className="px-5 py-10">
        <Loading lines={3} />
      </div>
    )
  }
  if (session.status === "anonymous") return <LoginPage />

  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Shell />}>
          <Route path="/" element={<RoundPage />} />
          <Route path="/orders/:id" element={<StopPage />} />
          <Route path="/pickups/:id" element={<RunPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
