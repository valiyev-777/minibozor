import { Navigate, Route, Routes } from "react-router-dom"
import { LoginPage } from "@/auth/LoginPage"
import { useSession } from "@/auth/session"
import { Shell } from "@/components/Shell"
import { CatalogPage } from "@/pages/CatalogPage"
import { DashboardPage } from "@/pages/DashboardPage"
import { OffersPage } from "@/pages/OffersPage"
import { ProductsPage } from "@/pages/ProductsPage"
import { StatementPage } from "@/pages/StatementPage"
import { StatementsPage } from "@/pages/StatementsPage"
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
        <Route path="/products" element={<ProductsPage />} />
        <Route path="/offers" element={<OffersPage />} />
        <Route path="/stock" element={<StockPage />} />
        <Route path="/supplies" element={<SuppliesPage />} />
        <Route path="/catalog" element={<CatalogPage />} />
        <Route path="/statements" element={<StatementsPage />} />
        {/* One period's account is long enough to be its own screen, and it
            is reached from a row rather than from the menu. */}
        <Route path="/statements/:id" element={<StatementPage />} />
        {/* Anything else goes to the dashboard rather than an empty frame. */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
