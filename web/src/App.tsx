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
import { PickupsPage } from "@/pages/pickups"
import { ReturnsPage } from "@/pages/returns"
import { SlotsPage } from "@/pages/delivery"
import { AuditPage } from "@/pages/audit"
import { CustomersPage } from "@/pages/customers"
import { CategoriesPage, CouriersPage } from "@/pages/people"
import { StaffPage } from "@/pages/staff"
import { ProductsPage } from "@/pages/products"
import { PublishPage } from "@/pages/publish"
import { ReportsPage } from "@/pages/reports"
import { LabelsPage } from "@/pages/labels"
import { PickingPage } from "@/pages/picking"
import { QabulPage } from "@/pages/qabul"
import { ShelfMapPage } from "@/pages/shelf-map"
import { canReach, homeFor } from "@/lib/nav"
import { useSession } from "@/lib/session"

export function App() {
  const { staff, loading } = useSession()

  if (loading) {
    return (
      <div className="grid min-h-full place-items-center text-ink-soft">Yuklanmoqda…</div>
    )
  }
  if (!staff || staff.role === "customer") return <LoginPage />

  const home = homeFor(staff.role)
  // `canReach` and nothing else: the menu nests one level now, so "is it in
  // the top-level list" stopped being the same question as "may this person
  // open it", and every screen filed under a drawer had its route quietly
  // not built. It walks the tree, and it still answers for the screens that
  // are reachable without being in a menu at all.
  const may = (to: string) => canReach(staff.role, to)

  return (
    <Routes>
      <Route element={<Shell />}>
        {may("/") ? (
          <Route index element={<DashboardPage />} />
        ) : (
          <Route index element={<Navigate to={home} replace />} />
        )}

        {/* ------------------------------------------------------------ ombor */}
        {may("/ombor") ? (
          <Route path="/ombor" element={<ShelfMapPage />} />
        ) : null}
        {may("/qabul") ? <Route path="/qabul" element={<QabulPage />} /> : null}
        {may("/terish") ? (
          <Route path="/terish" element={<PickingPage />} />
        ) : null}
        {may("/sanash") ? (
          <Route path="/sanash" element={<CountsPage />} />
        ) : null}
        {may("/yorliqlar") ? (
          <Route path="/yorliqlar" element={<LabelsPage />} />
        ) : null}

        {/* ------------------------------------------------------------ admin */}
        {may("/mahsulotlar") ? (
          <Route path="/mahsulotlar" element={<ProductsPage />} />
        ) : null}
        {may("/sotuvga-chiqarish") ? (
          <Route path="/sotuvga-chiqarish" element={<PublishPage />} />
        ) : null}
        {may("/kategoriyalar") ? (
          <Route path="/kategoriyalar" element={<CategoriesPage />} />
        ) : null}
        {may("/qaytarishlar") ? (
          <Route path="/qaytarishlar" element={<ReturnsPage />} />
        ) : null}
        {may("/olib-kelish") ? (
          <Route path="/olib-kelish" element={<PickupsPage />} />
        ) : null}
        {may("/yetkazish-oynalari") ? (
          <Route path="/yetkazish-oynalari" element={<SlotsPage />} />
        ) : null}
        {may("/buyurtmalar") ? (
          <Route path="/buyurtmalar" element={<OrdersPage />} />
        ) : null}
        {may("/kuryerlar") ? (
          <Route path="/kuryerlar" element={<CouriersPage />} />
        ) : null}
        {may("/xodimlar") ? (
          <Route path="/xodimlar" element={<StaffPage />} />
        ) : null}
        {may("/mijozlar") ? (
          <Route path="/mijozlar" element={<CustomersPage />} />
        ) : null}
        {may("/hisobotlar") ? (
          <Route path="/hisobotlar" element={<ReportsPage />} />
        ) : null}
        {may("/jurnal") ? <Route path="/jurnal" element={<AuditPage />} /> : null}

        {/* ---------------------------------------------------------- kuryer */}
        {may("/ishlarim") ? (
          <Route path="/ishlarim" element={<MyWorkPage />} />
        ) : null}
        {may("/tarix") ? (
          <Route path="/tarix" element={<CourierHistoryPage />} />
        ) : null}
        {may("/daromad") ? (
          <Route path="/daromad" element={<EarningsPage />} />
        ) : null}

        <Route path="*" element={<Navigate to={home} replace />} />
      </Route>
    </Routes>
  )
}
