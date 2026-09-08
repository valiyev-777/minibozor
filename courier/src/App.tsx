import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom"
import { Loading } from "@/ui/states"
import { LoginPage } from "@/auth/LoginPage"
import { useSession } from "@/auth/session"
import { Shell } from "@/components/Shell"
import { BoardPage } from "@/pages/BoardPage"
import { RoundPage } from "@/pages/RoundPage"
import { StopPage } from "@/pages/StopPage"
import { RunPage } from "@/pages/RunPage"
import { ProfilePage } from "@/pages/ProfilePage"

/**
 * Five screens: the board, my round, one delivery, one collection, my worth.
 *
 * The board is the one that changed the shape of this app. A courier used to
 * be handed a round and read it, so there was nowhere to go and no menu; they
 * choose their own work now, which is a place to be rather than a list to
 * read.
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
          <Route path="/board" element={<BoardPage />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="/orders/:id" element={<StopPage />} />
          <Route path="/pickups/:id" element={<RunPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
