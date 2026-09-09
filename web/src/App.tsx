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
import { LabelsPage } from "@/pages/labels"
import { PickingPage } from "@/pages/picking"
import { PutawayPage } from "@/pages/putaway"
import { QabulPage } from "@/pages/qabul"
import { ShelfMapPage } from "@/pages/shelf-map"
import { Soon } from "@/pages/soon"
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
          <Route
            index
            element={<Soon title="Boshqaruv" what="Raqamlar va grafik — 6-bosqichda." />}
          />
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
        {guard(allowed, "/mahsulotlar", "Mahsulotlar", "Kartalar, rang × o'lcham to'ri va rasmlar — 6-bosqichda.")}
        {guard(allowed, "/kategoriyalar", "Kategoriyalar", "Kategoriya daraxti — 6-bosqichda.")}
        {guard(allowed, "/buyurtmalar", "Buyurtmalar", "Buyurtmalar navbati — 6-bosqichda.")}
        {guard(allowed, "/kuryerlar", "Kuryerlar", "Kim nima olib ketdi — 6-bosqichda.")}
        {guard(allowed, "/xodimlar", "Xodimlar", "Rollar — 6-bosqichda.")}
        {guard(allowed, "/hisobotlar", "Hisobotlar", "Sotuv va ombor hisobotlari — 6-bosqichda.")}

        {/* ---------------------------------------------------------- kuryer */}
        {guard(allowed, "/ishlarim", "Mening ishlarim", "Olish, yetkazish, urinish — 6-bosqichda.")}
        {guard(allowed, "/tarix", "Tarix", "Yetkazilgan buyurtmalar — 6-bosqichda.")}
        {guard(allowed, "/daromad", "Daromad", "Kunlik va oylik daromad — 6-bosqichda.")}

        <Route path="*" element={<Navigate to={home} replace />} />
      </Route>
    </Routes>
  )
}

/** A route only when this role's navigation has it, so a URL typed by hand
 * lands on the role's own home rather than on a screen it may not read. */
function guard(allowed: Set<string>, path: string, title: string, what: string) {
  if (!allowed.has(path)) return null
  return (
    <Route key={path} path={path} element={<Soon title={title} what={what} />} />
  )
}
