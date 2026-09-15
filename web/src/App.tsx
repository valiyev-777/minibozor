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
import { KuryerShell } from "@/components/kuryer/shell"
import { KuryerConfirm } from "@/pages/kuryer/confirm"
import { KuryerEarnings } from "@/pages/kuryer/earnings"
import { KuryerHome } from "@/pages/kuryer/home"
import { KuryerPayment } from "@/pages/kuryer/payment"
import { KuryerProfile } from "@/pages/kuryer/profile"
import { KuryerRoute } from "@/pages/kuryer/route"
import { KuryerStop } from "@/pages/kuryer/stop"
import { KuryerTake } from "@/pages/kuryer/take"
import { LoginPage } from "@/pages/login"
import { NotFound } from "@/pages/oops"
import { CountsPage } from "@/pages/counts"
import { CourierHistoryPage, EarningsPage, MyWorkPage } from "@/pages/courier"
import { DashboardPage } from "@/pages/dashboard"
import { OrdersPage } from "@/pages/orders"
import { PickupsPage } from "@/pages/pickups"
import { ReturnsPage } from "@/pages/returns"
import { AuditPage } from "@/pages/audit"
import { CustomersPage } from "@/pages/customers"
import { CategoriesPage, CouriersPage } from "@/pages/people"
import { StaffPage } from "@/pages/staff"
import { ProductsPage } from "@/pages/products"
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
      {/* ------------------------------------------------------ the courier app
       *
       * A **sibling** of the back office's shell rather than a screen inside
       * it, and that is the one architectural decision this design forces. The
       * courier's screens are a full-bleed map with glass floating over it and
       * a tab bar of their own; the shell above them is a 264px rail, a
       * breadcrumb bar and `p-6` of grey canvas. Nesting one in the other
       * would mean every courier screen opening by undoing the frame it was
       * given — and a second navigation drawn under the first one on a phone.
       *
       * So there are two shells, the other roles' is untouched, and they share
       * everything below the chrome: the session, the query client, the theme
       * and `shared/theme.css`. See `components/kuryer/shell`.
       *
       * Guarded by role here rather than through `canReach`: the courier's
       * `navFor` entries are the *old* three screens, which still work — see
       * below — and this app is not in any menu.
       */}
      {staff.role === "courier" ? (
        <Route path="/kuryer" element={<KuryerShell />}>
          <Route index element={<KuryerHome />} />
          <Route path="olish" element={<KuryerTake />} />
          <Route path="marshrut" element={<KuryerRoute />} />
          <Route path="marshrut/:id" element={<KuryerStop />} />
          <Route path="marshrut/:id/tasdiq" element={<KuryerConfirm />} />
          <Route path="marshrut/:id/tolov" element={<KuryerPayment />} />
          <Route path="daromad" element={<KuryerEarnings />} />
          <Route path="profil" element={<KuryerProfile />} />
          <Route path="*" element={<Navigate to="/kuryer" replace />} />
        </Route>
      ) : null}

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
        {may("/kategoriyalar") ? (
          <Route path="/kategoriyalar" element={<CategoriesPage />} />
        ) : null}
        {may("/qaytarishlar") ? (
          <Route path="/qaytarishlar" element={<ReturnsPage />} />
        ) : null}
        {may("/olib-kelish") ? (
          <Route path="/olib-kelish" element={<PickupsPage />} />
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

        {/* ---------------------------------------------------------- kuryer
         *
         * The old three screens, kept and working, and reached from the rail
         * exactly as before. They are the *desk* view of the same work — an
         * owner opening a courier's account at a laptop to see what is in
         * their van gets a table rather than a map — and deleting them would
         * have meant a courier signing in at a desk landing in a phone app
         * stretched across a monitor.
         *
         * They are not in any tab of the new app and the new app is not in
         * this menu: two doors to one job, each the right shape for where it
         * is opened. The courier's own home is `/kuryer` now (`homeFor`), so
         * the map is what a phone lands on.
         */}
        {may("/ishlarim") ? (
          <Route path="/ishlarim" element={<MyWorkPage />} />
        ) : null}
        {may("/tarix") ? (
          <Route path="/tarix" element={<CourierHistoryPage />} />
        ) : null}
        {may("/daromad") ? (
          <Route path="/daromad" element={<EarningsPage />} />
        ) : null}

        {/* Said, not silently corrected. A wrong address that redirects
            home leaves somebody believing the link they were sent *is* the
            dashboard. */}
        <Route path="*" element={<NotFound home={home} />} />
      </Route>
    </Routes>
  )
}
