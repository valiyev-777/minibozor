import * as React from "react"
import { NavLink, Outlet } from "react-router-dom"
import {
  Boxes,
  LayoutDashboard,
  LogOut,
  Receipt,
  Search,
  Tag,
  Truck,
} from "lucide-react"
import { useSession } from "@/auth/session"
import { useShop } from "@/auth/shop"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

/**
 * A top bar, not a sidebar.
 *
 * The backoffice puts nine rows down the left because an operator lives in
 * one of them all day and needs the others one click away. A seller has four
 * screens and often opens this on a phone; a rail eats a third of that width
 * to show four items. So the navigation goes across the top and wraps.
 */
const NAV = [
  { to: "/", label: "Boshqaruv", icon: LayoutDashboard },
  { to: "/catalog", label: "Katalog", icon: Search },
  { to: "/offers", label: "Takliflarim", icon: Tag },
  { to: "/stock", label: "Qoldiq", icon: Boxes },
  { to: "/supplies", label: "Partiyalar", icon: Truck },
  { to: "/statements", label: "Hisobotlar", icon: Receipt },
]

export function Shell() {
  const session = useSession()
  const user = session.status === "signed-in" ? session.user : null
  const shop = useShop()

  return (
    <div className="flex min-h-full flex-col">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6">
          {/* The shop's name, not the platform's. A seller opening this wants
              to know which shop they are looking at before anything else —
              and the commission rate beside it, because every statement is
              computed from that figure and one they cannot read is one they
              cannot check. */}
          <div className="min-w-0">
            {shop.data ? (
              <>
                <p className="truncate text-[16px] font-semibold text-ink">
                  {shop.data.name}
                </p>
                <p className="text-[13px] text-ink-soft">
                  Komissiya{" "}
                  <span className="tabular font-medium text-brand-ink">
                    {shop.data.commission_percent}%
                  </span>
                  {shop.data.active ? null : (
                    <span className="ml-1.5 font-medium text-danger">· to'xtatilgan</span>
                  )}
                </p>
              </>
            ) : (
              <>
                <p className="text-[16px] font-semibold text-ink">Mini Bozor</p>
                <p className="text-[13px] text-ink-soft">Sotuvchi kabineti</p>
              </>
            )}
          </div>
          {user ? (
            <div className="flex items-center gap-3">
              {/* The phone once, not twice: a seller whose profile carries
                  no name would otherwise see their number stacked on itself. */}
              <div className="text-right">
                {user.full_name ? (
                  <>
                    <p className="truncate text-[14px] font-medium text-ink">
                      {user.full_name}
                    </p>
                    <p className="tabular text-[13px] text-ink-faint">{user.phone}</p>
                  </>
                ) : (
                  <p className="tabular text-[14px] font-medium text-ink">{user.phone}</p>
                )}
              </div>
              <Button size="sm" variant="ghost" onClick={() => void session.signOut()}>
                <LogOut />
                <span className="hidden sm:inline">Chiqish</span>
              </Button>
            </div>
          ) : null}
        </div>

        <nav className="mx-auto flex max-w-5xl gap-1 overflow-x-auto px-4 sm:px-6">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-2 border-b-2 px-3 py-2.5 text-[15px] whitespace-nowrap transition-colors",
                  isActive
                    ? "border-brand font-medium text-brand-ink"
                    : "border-transparent text-ink-soft hover:text-ink",
                )
              }
            >
              <item.icon className="size-4 shrink-0" />
              {item.label}
            </NavLink>
          ))}
        </nav>
      </header>

      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-6 sm:px-6">
        <Outlet />
      </main>
    </div>
  )
}

/** A page heading. One per screen, above the cards. */
export function PageHead({
  title,
  hint,
  actions,
}: {
  title: string
  hint?: React.ReactNode
  actions?: React.ReactNode
}) {
  return (
    <header className="mb-5 flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0">
        <h1 className="text-[22px] font-semibold text-ink">{title}</h1>
        {hint ? <p className="mt-1 max-w-2xl text-[14px] text-ink-soft">{hint}</p> : null}
      </div>
      {actions}
    </header>
  )
}
