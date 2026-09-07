import { Navigate, Route, Routes } from "react-router-dom"
import { useSession } from "./auth/session"
import { LoginPage } from "./auth/LoginPage"
import { OfflineProvider } from "./offline/OfflineProvider"
import { Shell } from "./components/Shell"
import { RoutePage } from "./pages/RoutePage"
import { OrderPage } from "./pages/OrderPage"
import { DeliverPage } from "./pages/DeliverPage"
import { FailPage } from "./pages/FailPage"
import { ShiftPage } from "./pages/ShiftPage"
import { PickupsPage } from "./pages/PickupsPage"
import { PickupRunPage } from "./pages/PickupRunPage"
import { OutboxPage } from "./pages/OutboxPage"

export default function App() {
  const session = useSession()

  if (session.status === "loading") {
    return (
      <div className="grid h-full place-items-center p-8 text-center text-lg text-muted">
        Yuklanmoqda…
      </div>
    )
  }

  if (session.status === "anonymous") return <LoginPage />

  // Signed in, or signed in and underground — the same application either way.
  // Everything below reads from the courier's own storage first.
  return (
    <OfflineProvider>
      <Routes>
        <Route element={<Shell />}>
          <Route path="/" element={<RoutePage />} />
          <Route path="/order/:id" element={<OrderPage />} />
          <Route path="/order/:id/deliver" element={<DeliverPage />} />
          <Route path="/order/:id/failed" element={<FailPage />} />
          <Route path="/shift" element={<ShiftPage />} />
          <Route path="/pickups" element={<PickupsPage />} />
          <Route path="/pickups/:id" element={<PickupRunPage />} />
          <Route path="/outbox" element={<OutboxPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </OfflineProvider>
  )
}
