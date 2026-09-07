import type * as React from "react"
import { Navigate, Route, Routes } from "react-router-dom"
import type { UserRole } from "@/api/types"
import { LoginPage } from "@/auth/LoginPage"
import { useSession } from "@/auth/session"
import { allowed, Layout } from "@/components/Layout"
import { CatalogPage } from "@/pages/CatalogPage"
import { CountsPage } from "@/pages/CountsPage"
import { ModerationPage } from "@/pages/ModerationPage"
import { MovementsPage } from "@/pages/MovementsPage"
import { OrdersPage } from "@/pages/OrdersPage"
import { ProductEditPage } from "@/pages/ProductEditPage"
import { RemovalsPage } from "@/pages/RemovalsPage"
import { ReturnsPage } from "@/pages/ReturnsPage"
import { ReviewsPage } from "@/pages/ReviewsPage"
import { SellersPage } from "@/pages/SellersPage"
import { ShelfPage } from "@/pages/ShelfPage"
import { ShowcasePage } from "@/pages/ShowcasePage"
import { SlotsPage } from "@/pages/SlotsPage"
import { SuppliesPage } from "@/pages/SuppliesPage"
import { UsersPage } from "@/pages/UsersPage"

/** The first screen of each role's day. */
const HOME: Partial<Record<UserRole, string>> = {
  warehouse: "/shelf",
  admin: "/moderation",
}

/**
 * What is behind each path in the sidebar.
 *
 * The paths themselves — and who may reach them — live in `NAV` in
 * `Layout.tsx`, so the menu and the router cannot disagree. A screen the
 * sidebar hides is a screen this map never mounts a route for, which is the
 * difference between not offering an operator the roles screen and not letting
 * them open it.
 */
const SCREENS: Record<string, React.ComponentType> = {
  "/returns": ReturnsPage,
  "/reviews": ReviewsPage,
  "/orders": OrdersPage,
  "/slots": SlotsPage,
  "/shelf": ShelfPage,
  "/supplies": SuppliesPage,
  "/counts": CountsPage,
  "/removals": RemovalsPage,
  "/movements": MovementsPage,
  "/moderation": ModerationPage,
  "/catalog": CatalogPage,
  "/sellers": SellersPage,
  "/users": UsersPage,
  "/showcase": ShowcasePage,
}

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

  // Where a role lands. The warehouse starts at the shelf, the admin at the
  // queue that is theirs alone, everybody else at the queue they work —
  // nobody should have to navigate away from a screen that is not theirs.
  const mine = allowed(session.user.role)
  const home = HOME[session.user.role] ?? mine[0]?.to ?? "/returns"

  return (
    <Routes>
      <Route element={<Layout />}>
        {mine.map((item) => {
          const Screen = SCREENS[item.to]
          return Screen ? (
            <Route key={item.to} path={item.to} element={<Screen />} />
          ) : null
        })}
        {/* The card editor hangs off the catalogue rather than the sidebar:
            it is reached from a row, not chosen from a menu, and it is open
            to whoever may see the catalogue. */}
        {mine.some((item) => item.to === "/catalog") ? (
          <Route path="/catalog/products/:id" element={<ProductEditPage />} />
        ) : null}
        {/* Anything else — a path for another role included — goes home
            rather than to an empty frame. */}
        <Route path="*" element={<Navigate to={home} replace />} />
      </Route>
    </Routes>
  )
}
