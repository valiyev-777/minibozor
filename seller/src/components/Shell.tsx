import * as React from "react"
import { NavLink, Outlet } from "react-router-dom"
import { Package, ReceiptText, Store, Undo2, Wallet } from "lucide-react"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/api/client"
import type { Listing, Return, Shop } from "@/api/types"
import { Button } from "@/ui/button"
import { cn } from "@/ui/cn"
import { useSession } from "@/auth/session"
import { Bell } from "./Bell"
import { t } from "@/lib/labels"

/**
 * The frame: which shop this is, where to go, and what is waiting.
 *
 * This was a row of four words under the header — a tab strip — and on a
 * laptop it read as the top of a website rather than the side of a tool: the
 * words sat in a line the eye skims past, nothing said which of them had work
 * behind it, and a shopkeeper opening the cabinet had no idea a customer had
 * asked for a refund an hour ago.
 *
 * So the same list is a **rail on a laptop and a bottom bar on a phone**, the
 * shape each device actually wants, and it carries counts. Both from one
 * array, because two lists drift.
 *
 * The counts are the reason the rail exists rather than a decoration on it.
 * "Waiting" is narrow on purpose — a refused product to fix, and a return
 * waiting on this seller's decision — because those are the two things where
 * nothing happens until *they* act. Orders are not counted: the warehouse and
 * the courier run those, and a badge on a screen where the seller has nothing
 * to do is a badge they learn to ignore, which is how they come to ignore the
 * one that matters.
 */
const LINKS = [
  { to: "/products", label: t.products, icon: Package, badge: "fix" },
  { to: "/orders", label: t.orders, icon: ReceiptText, badge: null },
  { to: "/returns", label: t.returns, icon: Undo2, badge: "returns" },
  { to: "/account", label: t.account, icon: Wallet, badge: null },
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

  const listings = useQuery({
    queryKey: ["listings"],
    queryFn: () => api<Listing[]>("/staff/catalog/listings"),
    staleTime: 60_000,
  })
  const returns = useQuery({
    queryKey: ["returns"],
    queryFn: () => api<Return[]>("/staff/returns"),
    staleTime: 60_000,
  })

  const counts: Record<string, number> = {
    fix: (listings.data ?? []).filter((row) => row.stage === "rejected").length,
    returns: (returns.data ?? []).filter(
      (row) => row.inspection && !row.seller_decision,
    ).length,
  }

  return (
    <div className="flex min-h-full flex-col lg:flex-row">
      {/* The rail, laptop only. */}
      <aside className="hidden shrink-0 border-r border-line bg-surface lg:sticky lg:top-0 lg:flex lg:h-screen lg:w-60 lg:flex-col">
        <div className="flex items-center gap-3 px-4 py-4">
          <span className="inline-flex size-9 shrink-0 items-center justify-center rounded-[var(--radius-control)] bg-brand-soft text-brand-deep">
            <Store className="size-5" />
          </span>
          <div className="min-w-0">
            <p className="truncate font-semibold text-ink">{shop.data?.name ?? t.app}</p>
            <p className="truncate text-[length:var(--text-micro)] text-ink-soft">
              {session.status === "signed-in" ? session.user.phone : ""}
            </p>
          </div>
        </div>
        <nav className="flex-1 px-2">
          <ul className="space-y-1">
            {LINKS.map((link) => (
              <li key={link.to}>
                <Tab link={link} count={(link.badge ? counts[link.badge] : 0) ?? 0} wide />
              </li>
            ))}
          </ul>
        </nav>
        <div className="p-3">
          <Button
            className="w-full"
            variant="ghost"
            size="sm"
            onClick={() => void session.signOut()}
          >
            {t.signOut}
          </Button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 border-b border-line bg-surface/95 backdrop-blur lg:border-b-0 lg:bg-transparent">
          <div className="mx-auto flex max-w-5xl items-center gap-3 px-[var(--gap-page)] py-3 lg:justify-end">
            <span className="inline-flex size-8 shrink-0 items-center justify-center rounded-[var(--radius-control)] bg-brand-soft text-brand-deep lg:hidden">
              <Store className="size-4" />
            </span>
            <div className="min-w-0 flex-1 lg:hidden">
              <p className="truncate text-[length:var(--text-body)] font-semibold text-ink">
                {shop.data?.name ?? t.app}
              </p>
              <p className="truncate text-[length:var(--text-micro)] text-ink-soft">
                {session.status === "signed-in" ? session.user.phone : ""}
              </p>
            </div>
            <Bell />
            <Button
              className="lg:hidden"
              variant="ghost"
              size="sm"
              onClick={() => void session.signOut()}
            >
              {t.signOut}
            </Button>
          </div>
        </header>

        <main className="flex-1 pb-28 lg:pb-10">
          <div className="mx-auto w-full max-w-5xl space-y-[var(--gap-page)] px-[var(--gap-page)] py-[var(--gap-page)]">
            <Outlet />
          </div>
        </main>
      </div>

      {/* The bar, phone only. Fixed, so a long list of products never puts the
          way out of this screen above the fold. */}
      <nav className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-surface/95 pb-safe backdrop-blur lg:hidden">
        <ul className="flex">
          {LINKS.map((link) => (
            <li key={link.to} className="flex-1">
              <Tab link={link} count={(link.badge ? counts[link.badge] : 0) ?? 0} />
            </li>
          ))}
        </ul>
      </nav>
    </div>
  )
}

function Tab({
  link,
  count,
  wide = false,
}: {
  link: (typeof LINKS)[number]
  count: number
  wide?: boolean
}) {
  const Icon = link.icon
  return (
    <NavLink
      to={link.to}
      className={({ isActive }) =>
        cn(
          "outline-none transition-colors focus-visible:ring-2 focus-visible:ring-brand/40",
          wide
            ? "flex items-center gap-3 rounded-[var(--radius-control)] px-3 py-2.5 text-[length:var(--text-body)] font-medium"
            : "flex flex-col items-center gap-1 py-2.5 text-[length:var(--text-micro)] font-medium",
          isActive
            ? wide
              ? "bg-brand-soft text-brand-deep"
              : "text-brand-deep"
            : "text-ink-soft",
        )
      }
    >
      <span className="relative">
        <Icon className={wide ? "size-5" : "size-6"} />
        {/* Nought is an absent badge. A number that is always on is a number
            nobody reads, and these two are meant to be read. */}
        {count > 0 ? (
          <span
            className="absolute -right-2 -top-1.5 inline-flex min-w-4 justify-center rounded-full
                       bg-danger px-1 text-[11px] font-semibold leading-4 text-danger-ink
                       tabular-nums"
          >
            {count}
          </span>
        ) : null}
      </span>
      <span className={wide ? "flex-1 truncate" : "truncate"}>{link.label}</span>
    </NavLink>
  )
}

/**
 * A screen's heading, and the one thing to do on it.
 *
 * Here rather than in each page so the four screens cannot each invent their
 * own spacing above the first panel.
 */
export function PageTitle({
  children,
  action,
}: {
  children: React.ReactNode
  action?: React.ReactNode
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <h1 className="text-xl font-semibold text-ink">{children}</h1>
      {action}
    </div>
  )
}
