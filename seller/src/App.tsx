import { Navigate, Route, Routes } from "react-router-dom"
import { LoginPage } from "@/auth/LoginPage"
import { useSession } from "@/auth/session"
import { Shell } from "@/components/Shell"
import { DashboardPage } from "@/pages/DashboardPage"
import { OffersPage } from "@/pages/OffersPage"
import { StockPage } from "@/pages/StockPage"
import { SuppliesPage } from "@/pages/SuppliesPage"

export function App() {
  const session = useSession()

  if (session.status === "loading") {
    return (
      <div className="flex min-h-full items-center justify-center">
        <p className="text-[15px] text-ink-faint">Yuklanmoqda…</p>
      </div>
    )
  }

  if (session.status === "anonymous") {
    return <LoginPage {...(session.reason ? { reason: session.reason } : {})} />
  }

  return (
    <Routes>
      <Route element={<Shell />}>
        <Route index element={<DashboardPage />} />
        <Route path="/offers" element={<OffersPage />} />
        <Route path="/stock" element={<StockPage />} />
        <Route path="/supplies" element={<SuppliesPage />} />
        {/* Statements and proposing a product are the next stage; anything
            else goes to the dashboard rather than to an empty frame. */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
