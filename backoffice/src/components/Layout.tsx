import { NavLink, Outlet } from "react-router-dom"
import { CalendarClock, LogOut, PackageCheck, Star, Undo2 } from "lucide-react"
import type { UserRole } from "@/api/types"
import { useSession } from "@/auth/session"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ROLE } from "@/lib/labels"
import { cn } from "@/lib/utils"

/**
 * The menu is data, and the role decides which of it exists.
 *
 * Four more panels hang off this: warehouse, admin, seller, and a courier app.
 * They will add rows here rather than fork the layout, which is why a row
 * carries the roles it belongs to instead of the sidebar carrying an `if`.
 */
type NavItem = {
  to: string
  label: string
  icon: typeof Undo2
  roles: UserRole[]
}

const NAV: NavItem[] = [
  { to: "/returns", label: "Qaytarishlar", icon: Undo2, roles: ["operator", "admin"] },
  { to: "/reviews", label: "Sharhlar", icon: Star, roles: ["operator", "admin"] },
  { to: "/orders", label: "Buyurtmalar", icon: PackageCheck, roles: ["operator", "admin"] },
  {
    to: "/slots",
    label: "Yetkazish oynalari",
    icon: CalendarClock,
    roles: ["operator", "admin"],
  },
]

export function Layout() {
  const session = useSession()
  const user = session.status === "signed-in" ? session.user : null
  const items = NAV.filter((item) => user && item.roles.includes(user.role))

  return (
    <div className="flex min-h-full">
      <aside className="flex w-52 shrink-0 flex-col bg-rail text-rail-ink">
        <div className="px-3 py-3.5">
          <p className="text-[13px] font-semibold text-white">Mini Bozor</p>
          <p className="text-[11px] text-rail-ink/70">Backoffice</p>
        </div>

        <nav className="flex-1 space-y-0.5 px-2">
          {items.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-2 rounded px-2 py-1.5 text-[13px] transition-colors",
                  isActive
                    ? "bg-white/12 font-medium text-white"
                    : "hover:bg-white/8 hover:text-white",
                )
              }
            >
              <item.icon className="size-3.5 shrink-0" />
              {item.label}
            </NavLink>
          ))}
        </nav>

        {user ? (
          <div className="border-t border-white/10 px-3 py-3">
            <p className="truncate text-[12px] font-medium text-white">
              {user.full_name || user.phone}
            </p>
            <p className="tabular truncate text-[11px] text-rail-ink/70">{user.phone}</p>
            <div className="mt-1.5 flex items-center justify-between gap-2">
              <Badge tone="accent">{ROLE[user.role]}</Badge>
              <Button
                size="sm"
                variant="ghost"
                className="text-rail-ink hover:bg-white/10 hover:text-white"
                onClick={() => void session.signOut()}
              >
                <LogOut />
                Chiqish
              </Button>
            </div>
          </div>
        ) : null}
      </aside>

      <main className="min-w-0 flex-1 overflow-x-hidden">
        <Outlet />
      </main>
    </div>
  )
}

export function Page({
  title,
  hint,
  actions,
  children,
}: {
  title: string
  hint?: string
  actions?: React.ReactNode
  children: React.ReactNode
}) {
  return (
    <div className="px-5 py-4">
      <header className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-[15px] font-semibold text-ink">{title}</h1>
          {hint ? <p className="text-[12px] text-ink-soft">{hint}</p> : null}
        </div>
        {actions}
      </header>
      {children}
    </div>
  )
}
