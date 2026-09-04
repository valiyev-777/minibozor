import { Navigate, Route, Routes } from "react-router-dom"
import { LoginPage } from "@/auth/LoginPage"
import { useSession } from "@/auth/session"
import { Layout } from "@/components/Layout"
import { CountsPage } from "@/pages/CountsPage"
import { MovementsPage } from "@/pages/MovementsPage"
import { OrdersPage } from "@/pages/OrdersPage"
import { RemovalsPage } from "@/pages/RemovalsPage"
import { ReturnsPage } from "@/pages/ReturnsPage"
import { ReviewsPage } from "@/pages/ReviewsPage"
import { ShelfPage } from "@/pages/ShelfPage"
import { SlotsPage } from "@/pages/SlotsPage"
import { SuppliesPage } from "@/pages/SuppliesPage"

export function App() {
  const session = useSession()

  if (session.status === "loading") {
    return (
      <div className="flex min-h-full items-center justify-center">
        <p className="text-[13px] text-ink-faint">Yuklanmoqda…</p>
      </div>
    )
  }

  if (session.status === "anonymous") {
    return <LoginPage {...(session.reason ? { reason: session.reason } : {})} />
  }

  // Where a role lands. The warehouse starts at the shelf, everybody else at
  // the queue they work — nobody should have to navigate away from a screen
  // that is not theirs.
  const home = session.user.role === "warehouse" ? "/shelf" : "/returns"

  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/returns" element={<ReturnsPage />} />
        <Route path="/reviews" element={<ReviewsPage />} />
        <Route path="/orders" element={<OrdersPage />} />
        <Route path="/slots" element={<SlotsPage />} />
        <Route path="/shelf" element={<ShelfPage />} />
        <Route path="/supplies" element={<SuppliesPage />} />
        <Route path="/counts" element={<CountsPage />} />
        <Route path="/removals" element={<RemovalsPage />} />
        <Route path="/movements" element={<MovementsPage />} />
        <Route path="*" element={<Navigate to={home} replace />} />
      </Route>
    </Routes>
  )
}
