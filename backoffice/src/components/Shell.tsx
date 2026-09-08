import * as React from "react"
import { NavLink, Outlet } from "react-router-dom"
import { Building2 } from "lucide-react"
import { Button } from "@/ui/button"
import { cn } from "@/ui/cn"
import { useSession, useStaff } from "@/auth/session"
import { Bell } from "./Bell"
import { menuFor } from "@/lib/nav"
import { useQueueCounts } from "@/lib/queues"
import { roleName, t } from "@/lib/labels"

/**
 * A rail, because this is the one panel with enough screens to need one.
 *
 * The seller has six links and puts them in a row; the warehouse, the
 * operator and the admin have between five and eleven, and a row of eleven is
 * a row nobody reads. It is a column on a desk and collapses to a scrolling
 * row on a narrow screen — a picker checking a batch on a tablet is a real
 * thing, and a drawer for five links would be a tap in the way.
 *
 * **The menu is `menuFor(role)` and nothing else.** A row a role may not open
 * is not greyed out here — it is absent, because a disabled row is an
 * invitation to ask why. The same table guards the routes, so the two cannot
 * disagree.
 */
export function Shell() {
  const session = useSession()
  const staff = useStaff()
  const rows = menuFor(staff.role)
  // What is waiting, per row. The warehouse lands on Qabul qilish; an order
  // placed a minute ago is on another screen, and until these numbers existed
  // nothing said so.
  const waiting = useQueueCounts(staff.role)

  return (
    <div className="flex min-h-full flex-col lg:flex-row">
      <aside
        className="shrink-0 border-b border-line bg-rail text-rail-ink
                   lg:h-screen lg:w-56 lg:border-b-0 lg:border-r lg:sticky lg:top-0"
      >
        <div className="flex items-center gap-2 px-4 py-3">
          <span className="inline-flex size-7 shrink-0 items-center justify-center rounded-[var(--radius-control)] bg-white/10">
            <Building2 className="size-4" />
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-[length:var(--text-small)] font-semibold text-white">
              {t.app}
            </p>
            <p className="truncate text-[length:var(--text-micro)]">
              {roleName[staff.role] ?? staff.role}
            </p>
          </div>
        </div>

        <nav className="px-2 pb-2 lg:pb-4">
          <ul className="flex gap-1 overflow-x-auto lg:flex-col lg:overflow-visible">
            {rows.map((row) => (
              <li key={row.path} className="shrink-0 lg:shrink">
                <NavLink
                  to={row.path}
                  end={row.path === "/"}
                  className={({ isActive }) =>
                    cn(
                      "block whitespace-nowrap rounded-[var(--radius-control)] px-3",
                      "py-[calc(var(--cell-y)*1.5)] text-[length:var(--text-small)] font-medium",
                      "transition-colors",
                      isActive
                        ? "bg-white/15 text-white"
                        : "hover:bg-white/10 hover:text-white",
                    )
                  }
                >
                  <span className="flex items-center gap-2">
                    <span className="flex-1">{row.label}</span>
                    {/* Nought is absent, not a zero. A badge on every row is
                        a badge nobody reads. */}
                    {waiting[row.path] ? (
                      <span
                        className="inline-flex min-w-5 justify-center rounded-full bg-brand px-1.5
                                   text-[length:var(--text-micro)] font-semibold text-brand-ink
                                   tabular-nums"
                      >
                        {waiting[row.path]}
                      </span>
                    ) : null}
                  </span>
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex items-center justify-end gap-2 border-b border-line bg-surface/95 px-[var(--gap-page)] py-2 backdrop-blur">
          <span className="mr-auto truncate text-[length:var(--text-small)] text-ink-soft">
            {staff.full_name || staff.phone}
          </span>
          <Bell />
          <Button variant="ghost" size="sm" onClick={() => void session.signOut()}>
            {t.signOut}
          </Button>
        </header>

        <main className="flex-1 space-y-[var(--gap-page)] px-[var(--gap-page)] py-[var(--gap-page)]">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

/** A page heading, above whatever the page is. */
export function PageTitle({
  children,
  action,
}: {
  children: React.ReactNode
  action?: React.ReactNode
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <h1 className="text-base font-semibold text-ink">{children}</h1>
      {action}
    </div>
  )
}
