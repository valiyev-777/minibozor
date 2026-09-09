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
        {guard(allowed, "/ombor", "Ombor xaritasi", "Xona, uch javon va ish joylari — 5-bosqichda.")}
        {guard(allowed, "/qabul", "Qabul", "Qoplar va saralash — 5-bosqichda.")}
        {guard(allowed, "/joylashtirish", "Joylashtirish", "QABUL navbati va katak kodi — 5-bosqichda.")}
        {guard(allowed, "/terish", "Terish", "Terish navbati va yurish tartibi — 5-bosqichda.")}
        {guard(allowed, "/sanash", "Sanash", "Katakni qayta sanash — 5-bosqichda.")}
        {guard(allowed, "/yorliqlar", "Yorliqlar", "A4 yorliq varag'i — 5-bosqichda.")}

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
