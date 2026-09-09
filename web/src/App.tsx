/**
 * Every route in the app, and who may reach it.
 *
 * The list is deliberately flat and readable: a route table split across
 * files is a route table nobody can answer "what screens are there" from.
 * Guarding is per role and matches the server's own — the API refuses
 * whatever this forgets, so a bug here is a wasted request rather than a leak.
 */

import { Navigate, Route, Routes } from "react-router-dom"

import { Shell } from "@/components/shell"
import { LoginPage } from "@/pages/login"
import { CountsPage } from "@/pages/counts"
import { CourierHistoryPage, EarningsPage, MyWorkPage } from "@/pages/courier"
import { DashboardPage } from "@/pages/dashboard"
import { OrdersPage } from "@/pages/orders"
import { CategoriesPage, CouriersPage, StaffPage } from "@/pages/people"
import { ProductsPage } from "@/pages/products"
import { PublishPage } from "@/pages/publish"
import { ReportsPage } from "@/pages/reports"
import { LabelsPage } from "@/pages/labels"
import { PickingPage } from "@/pages/picking"
import { PutawayPage } from "@/pages/putaway"
import { QabulPage } from "@/pages/qabul"
import { ShelfMapPage } from "@/pages/shelf-map"
import { homeFor, navFor } from "@/lib/nav"
import { useSession } from "@/lib/session"

export function App() {
  const { staff, loading } = useSession()

  if (loading) {
    return (
      <div className="grid min-h-full place-items-center text-ink-soft">Yuklanmoqda…</div>
    )
  }
  if (!staff || staff.role === "customer") return <LoginPage />

  const allowed = new Set(navFor(staff.role).map((item) => item.to))
  const home = homeFor(staff.role)

  return (
    <Routes>
      <Route element={<Shell />}>
        {allowed.has("/") ? (
          <Route index element={<DashboardPage />} />
        ) : (
          <Route index element={<Navigate to={home} replace />} />
        )}

        {/* ------------------------------------------------------------ ombor */}
        {allowed.has("/ombor") ? (
          <Route path="/ombor" element={<ShelfMapPage />} />
        ) : null}
        {allowed.has("/qabul") ? (
          <Route path="/qabul" element={<QabulPage />} />
        ) : null}
        {allowed.has("/joylashtirish") ? (
          <Route path="/joylashtirish" element={<PutawayPage />} />
        ) : null}
        {allowed.has("/terish") ? (
          <Route path="/terish" element={<PickingPage />} />
        ) : null}
        {allowed.has("/sanash") ? (
          <Route path="/sanash" element={<CountsPage />} />
        ) : null}
        {allowed.has("/yorliqlar") ? (
          <Route path="/yorliqlar" element={<LabelsPage />} />
        ) : null}

        {/* ------------------------------------------------------------ admin */}
        {allowed.has("/mahsulotlar") ? (
          <Route path="/mahsulotlar" element={<ProductsPage />} />
        ) : null}
        {allowed.has("/sotuvga-chiqarish") ? (
          <Route path="/sotuvga-chiqarish" element={<PublishPage />} />
        ) : null}
        {allowed.has("/kategoriyalar") ? (
          <Route path="/kategoriyalar" element={<CategoriesPage />} />
        ) : null}
        {allowed.has("/buyurtmalar") ? (
          <Route path="/buyurtmalar" element={<OrdersPage />} />
        ) : null}
        {allowed.has("/kuryerlar") ? (
          <Route path="/kuryerlar" element={<CouriersPage />} />
        ) : null}
        {allowed.has("/xodimlar") ? (
          <Route path="/xodimlar" element={<StaffPage />} />
        ) : null}
        {allowed.has("/hisobotlar") ? (
          <Route path="/hisobotlar" element={<ReportsPage />} />
        ) : null}

        {/* ---------------------------------------------------------- kuryer */}
        {allowed.has("/ishlarim") ? (
          <Route path="/ishlarim" element={<MyWorkPage />} />
        ) : null}
        {allowed.has("/tarix") ? (
          <Route path="/tarix" element={<CourierHistoryPage />} />
        ) : null}
        {allowed.has("/daromad") ? (
          <Route path="/daromad" element={<EarningsPage />} />
        ) : null}

        <Route path="*" element={<Navigate to={home} replace />} />
      </Route>
    </Routes>
  )
}
