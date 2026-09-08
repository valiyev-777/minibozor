import * as React from "react"
import { NavLink, Outlet } from "react-router-dom"
import { Store } from "lucide-react"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/api/client"
import type { Shop } from "@/api/types"
import { Button } from "@/ui/button"
import { cn } from "@/ui/cn"
import { useSession } from "@/auth/session"
import { Bell } from "./Bell"
import { t } from "@/lib/labels"

/**
 * The frame: which shop this is, where to go, and the bell.
 *
 * Six screens and no sub-navigation, so the nav is one row of links rather
 * than the backoffice's rail. It scrolls sideways on a narrow phone instead of
 * collapsing into a menu — a shopkeeper checking their returns on a handset
 * should not have to open a drawer to find six words, and the row is the
 * whole map of the application.
 */
const LINKS = [
  { to: "/products", label: t.products },
  { to: "/supplies", label: t.supplies },
  { to: "/orders", label: t.orders },
  { to: "/returns", label: t.returns },
  { to: "/account", label: t.account },
] as const

export function Shell() {
  const session = useSession()

  // Which shop, which is not what `/staff/me` answers: that gives the user —
  // a phone and a role — and the name over the door is on the `sellers` row.
  const shop = useQuery({
    queryKey: ["shop"],
    queryFn: () => api<Shop>("/staff/sellers/me"),
    staleTime: 5 * 60_000,
  })

  return (
    <div className="flex min-h-full flex-col">
      <header className="sticky top-0 z-30 border-b border-line bg-surface/95 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center gap-3 px-[var(--gap-page)] py-3">
          <span className="inline-flex size-8 shrink-0 items-center justify-center rounded-[var(--radius-control)] bg-brand-soft text-brand-deep">
            <Store className="size-4" />
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-[length:var(--text-body)] font-semibold text-ink">
              {shop.data?.name ?? t.app}
            </p>
            <p className="truncate text-[length:var(--text-micro)] text-ink-soft">
              {session.status === "signed-in" ? session.user.phone : ""}
            </p>
          </div>
          <Bell />
          <Button variant="ghost" size="sm" onClick={() => void session.signOut()}>
            {t.signOut}
          </Button>
        </div>
        <nav className="mx-auto max-w-5xl overflow-x-auto px-[var(--gap-page)]">
          <ul className="flex min-w-max gap-1 pb-1">
            {LINKS.map((link) => (
              <li key={link.to}>
                <NavLink
                  to={link.to}
                  className={({ isActive }) =>
                    cn(
                      "-mb-px inline-flex h-9 items-center rounded-t-[var(--radius-control)] px-3",
                      "border-b-2 text-[length:var(--text-small)] font-medium transition-colors",
                      isActive
                        ? "border-brand text-brand-deep"
                        : "border-transparent text-ink-soft hover:text-ink",
                    )
                  }
                >
                  {link.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
      </header>

      <main className="mx-auto w-full max-w-5xl flex-1 space-y-[var(--gap-page)] px-[var(--gap-page)] py-[var(--gap-page)]">
        <Outlet />
      </main>
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
      <h1 className="text-lg font-semibold text-ink">{children}</h1>
      {action}
    </div>
  )
}
