import * as React from "react"
import { NavLink, Outlet } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import {
  BadgeCheck,
  CalendarClock,
  ClipboardList,
  Layers,
  LayoutTemplate,
  LibraryBig,
  LogOut,
  PackageCheck,
  ScrollText,
  Star,
  Store,
  Truck,
  Undo2,
  Users,
} from "lucide-react"
import { api } from "@/api/client"
import type { CatalogSummary, UserRole } from "@/api/types"
import { useSession } from "@/auth/session"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ROLE } from "@/lib/labels"
import { cn } from "@/lib/utils"

/**
 * The menu is data, and the role decides which of it exists.
 *
 * Two more panels hang off this: seller, and a courier app. They will add rows
 * here rather than fork the layout, which is why a row carries the roles it
 * belongs to instead of the sidebar carrying an `if`.
 *
 * The router reads the same rows — see `allowed` below and `App.tsx`. A menu
 * that hides a screen while the URL still opens it has not withheld anything:
 * a bookmark, the back button or a pasted link gets an operator on to the
 * roles screen. One list decides both.
 */
export type NavItem = {
  to: string
  label: string
  icon: typeof Undo2
  roles: UserRole[]
  /** Starts a group in the rail, so nine rows read as three jobs. */
  group?: string
  /** Shows a count beside the label. Only the queues have one. */
  badge?: "moderating"
}

export const NAV: NavItem[] = [
  {
    to: "/returns",
    label: "Qaytarishlar",
    icon: Undo2,
    roles: ["operator", "admin"],
    group: "Operator",
  },
  { to: "/reviews", label: "Sharhlar", icon: Star, roles: ["operator", "admin"] },
  { to: "/orders", label: "Buyurtmalar", icon: PackageCheck, roles: ["operator", "admin"] },
  {
    to: "/slots",
    label: "Yetkazish oynalari",
    icon: CalendarClock,
    roles: ["operator", "admin"],
  },
  {
    to: "/shelf",
    label: "Javon",
    icon: Layers,
    roles: ["warehouse", "admin"],
    group: "Ombor",
  },
  { to: "/supplies", label: "Partiyalar", icon: Truck, roles: ["warehouse", "admin"] },
  {
    to: "/counts",
    label: "Inventarizatsiya",
    icon: ClipboardList,
    roles: ["warehouse", "admin"],
  },
  { to: "/removals", label: "Qaytarib olish", icon: Undo2, roles: ["warehouse", "admin"] },
  {
    to: "/movements",
    label: "Harakatlar",
    icon: ScrollText,
    roles: ["warehouse", "admin"],
  },
  {
    to: "/moderation",
    label: "Moderatsiya",
    icon: BadgeCheck,
    roles: ["admin"],
    group: "Administrator",
    badge: "moderating",
  },
  { to: "/catalog", label: "Katalog", icon: LibraryBig, roles: ["admin"] },
  { to: "/sellers", label: "Sotuvchilar", icon: Store, roles: ["admin"] },
  { to: "/users", label: "Foydalanuvchilar", icon: Users, roles: ["admin"] },
  { to: "/showcase", label: "Vitrina", icon: LayoutTemplate, roles: ["admin"] },
]

/** The rows this role may reach, for the sidebar and for the router alike. */
export function allowed(role: UserRole): NavItem[] {
  return NAV.filter((item) => item.roles.includes(role))
}

export function Layout() {
  const session = useSession()
  const user = session.status === "signed-in" ? session.user : null
  const items = user ? allowed(user.role) : []

  // Headings only when there is more than one job on screen. An operator sees
  // four rows that are all theirs, and a heading over them names something
  // they cannot leave; an admin sees three panels stacked and needs to know
  // where one ends.
  const grouped = new Set(items.map((item) => item.group).filter(Boolean)).size > 1

  // One integer, from one GROUP BY. The queue itself is a page of cards, and
  // the sidebar is on every screen — fetching it to render "3" would download
  // the moderation queue on the way to the delivery windows.
  const summary = useQuery({
    queryKey: ["staff", "catalog", "summary"],
    queryFn: () => api<CatalogSummary>("/staff/catalog/summary"),
    enabled: items.some((item) => item.badge),
    refetchInterval: 60_000,
  })
  const waiting = summary.data?.counts["moderating"] ?? 0

  return (
    <div className="flex min-h-full">
      <aside className="flex w-52 shrink-0 flex-col bg-rail text-rail-ink">
        <div className="px-3 py-3.5">
          <p className="text-[13px] font-semibold text-white">Mini Bozor</p>
          <p className="text-[11px] text-rail-ink/70">Backoffice</p>
        </div>

        <nav className="flex-1 space-y-0.5 overflow-y-auto px-2 pb-2">
          {items.map((item) => (
            <React.Fragment key={item.to}>
              {/* A heading only where a group actually begins: an operator who
                  cannot see the warehouse rows should not see its heading
                  either, and the admin — who sees all three — needs them. */}
              {grouped && item.group ? (
                <p className="px-2 pt-3 pb-1 text-[10px] font-semibold tracking-wide text-rail-ink/50 uppercase">
                  {item.group}
                </p>
              ) : null}
              <NavLink
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
                <span className="flex-1 truncate">{item.label}</span>
                {item.badge && waiting ? (
                  <span className="tabular rounded bg-white/15 px-1 text-[11px] font-semibold text-white">
                    {waiting}
                  </span>
                ) : null}
              </NavLink>
            </React.Fragment>
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
  floor,
  children,
}: {
  title: string
  hint?: string
  actions?: React.ReactNode
  /**
   * Warehouse density: bigger type and taller rows, for a tablet held at
   * arm's length by somebody wearing gloves. Not a second design system —
   * the same tokens and the same table, scaled.
   */
  floor?: boolean
  children: React.ReactNode
}) {
  return (
    <div className={cn("px-5 py-4", floor && "floor")}>
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
