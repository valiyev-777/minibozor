import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom"
import { Loading } from "@/ui/states"
import { LoginPage } from "@/auth/LoginPage"
import { useSession, useStaff } from "@/auth/session"
import { Shell } from "@/components/Shell"
import { allowed, homeFor, SCREENS } from "@/lib/nav"
import { OverviewPage } from "@/pages/OverviewPage"
import { SuppliesPage } from "@/pages/SuppliesPage"
import { SupplyPage } from "@/pages/SupplyPage"
import { OrdersPage } from "@/pages/OrdersPage"
import { OrderPage } from "@/pages/OrderPage"
import { PickupsPage } from "@/pages/PickupsPage"
import { RemovalsPage } from "@/pages/RemovalsPage"
import { StockPage } from "@/pages/StockPage"
import { ReturnsPage } from "@/pages/ReturnsPage"
import { ReturnPage } from "@/pages/ReturnPage"
import { SellersPage } from "@/pages/SellersPage"
import { UsersPage } from "@/pages/UsersPage"
import { CatalogPage } from "@/pages/CatalogPage"
import { ProductEditPage } from "@/pages/ProductEditPage"

/**
 * The routes, guarded by the same table that draws the menu.
 *
 * `SCREENS` says who may open what, so a path a role cannot open sends them to
 * their own landing screen instead of rendering something they will get a 403
 * from. That matters because the paths are typed and bookmarked: somebody
 * hands a picker a link to `/sellers` and the picker should end up somewhere
 * useful, not at an error.
 *
 * Nothing behind the guard is mounted before there is a session, so a screen's
 * query cannot fire while the token is still being recovered from the refresh
 * cookie — that used to produce a 401, a retry and a flash of the login page
 * on every reload.
 */
const ELEMENTS: Record<string, React.ReactNode> = {
  "/": <OverviewPage />,
  "/supplies": <SuppliesPage />,
  "/supplies/:id": <SupplyPage />,
  "/orders": <OrdersPage />,
  "/orders/:id": <OrderPage />,
  "/pickups": <PickupsPage />,
  "/removals": <RemovalsPage />,
  "/stock": <StockPage />,
  "/returns": <ReturnsPage />,
  "/returns/:id": <ReturnPage />,
  "/sellers": <SellersPage />,
  "/users": <UsersPage />,
  "/catalog": <CatalogPage />,
  "/products/:id/edit": <ProductEditPage />,
}

export function App() {
  const session = useSession()

  if (session.status === "loading") {
    return (
      <div className="px-5 py-10">
        <Loading lines={4} />
      </div>
    )
  }
  if (session.status === "anonymous") return <LoginPage />

  return (
    <BrowserRouter>
      <Inside />
    </BrowserRouter>
  )
}

function Inside() {
  const role = useStaff().role
  const home = homeFor(role)

  return (
    <Routes>
      <Route element={<Shell />}>
        {SCREENS.map((screen) => (
          <Route
            key={screen.path}
            path={screen.path}
            element={
              allowed(screen, role) ? (
                ELEMENTS[screen.path]
              ) : (
                <Navigate to={home} replace />
              )
            }
          />
        ))}
        <Route path="*" element={<Navigate to={home} replace />} />
      </Route>
    </Routes>
  )
}
