import { Navigate, Route, Routes } from "react-router-dom"
import { BrowserRouter } from "react-router-dom"
import { Loading } from "@/ui/states"
import { LoginPage } from "@/auth/LoginPage"
import { useSession } from "@/auth/session"
import { Shell } from "@/components/Shell"
import { ProductsPage } from "@/pages/ProductsPage"
import { NewProductPage } from "@/pages/NewProductPage"
import { ProductPage } from "@/pages/ProductPage"
import { OrdersPage } from "@/pages/OrdersPage"
import { ReturnsPage } from "@/pages/ReturnsPage"
import { AccountPage } from "@/pages/AccountPage"

/**
 * Six screens, and nothing behind the guard is mounted before there is a
 * session.
 *
 * The routes are inside the signed-in branch rather than wrapped in a
 * `<RequireAuth>` element, so a screen's query cannot fire while the token is
 * still being recovered from the refresh cookie — that used to produce a 401,
 * a retry and a flash of the login page on every reload.
 */
export function App() {
  const session = useSession()

  if (session.status === "loading") {
    return (
      <div className="mx-auto max-w-5xl px-5 py-10">
        <Loading lines={4} />
      </div>
    )
  }

  if (session.status === "anonymous") return <LoginPage />

  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Shell />}>
          <Route path="/products" element={<ProductsPage />} />
          <Route path="/products/new" element={<NewProductPage />} />
          <Route path="/products/:id" element={<ProductPage />} />
          <Route path="/orders" element={<OrdersPage />} />
          <Route path="/returns" element={<ReturnsPage />} />
          <Route path="/account" element={<AccountPage />} />
          {/* Products is the home screen: it is the one a seller opens to
              answer "did my things arrive and are they selling". */}
          <Route path="*" element={<Navigate to="/products" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
