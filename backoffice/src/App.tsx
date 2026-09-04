import { Navigate, Route, Routes } from "react-router-dom"
import { LoginPage } from "@/auth/LoginPage"
import { useSession } from "@/auth/session"
import { Layout } from "@/components/Layout"
import { OrdersPage } from "@/pages/OrdersPage"
import { ReturnsPage } from "@/pages/ReturnsPage"
import { ReviewsPage } from "@/pages/ReviewsPage"
import { SlotsPage } from "@/pages/SlotsPage"

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

  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/returns" element={<ReturnsPage />} />
        <Route path="/reviews" element={<ReviewsPage />} />
        <Route path="/orders" element={<OrdersPage />} />
        <Route path="/slots" element={<SlotsPage />} />
        <Route path="*" element={<Navigate to="/returns" replace />} />
      </Route>
    </Routes>
  )
}
