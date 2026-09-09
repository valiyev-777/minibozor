/**
 * The frame every screen sits in.
 *
 * A rail on a desktop and a bar along the bottom on a phone — not two layouts
 * so much as one navigation drawn where the hand is. Half the people using
 * this are standing up holding something.
 */

import { LogOut, Menu, X } from "lucide-react"
import { useState } from "react"
import { NavLink, Outlet } from "react-router-dom"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/cn"
import { densityFor, navFor } from "@/lib/nav"
import { useSession } from "@/lib/session"

export function Shell() {
  const { staff, signOut } = useSession()
  const [open, setOpen] = useState(false)
  if (!staff) return null

  const items = navFor(staff.role)

  return (
    <div className={cn("flex min-h-full flex-col md:flex-row", densityFor(staff.role))}>
      {/* ------------------------------------------------------------- the rail */}
      <aside className="no-print hidden w-60 shrink-0 flex-col bg-rail text-rail-ink md:flex">
        <Brand />
        <nav className="flex-1 space-y-1 px-3 py-2">
          {items.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-control px-3 text-small transition-colors",
                  "h-control hover:bg-white/10",
                  isActive && "bg-brand text-brand-ink hover:bg-brand",
                )
              }
            >
              <item.icon className="size-4 shrink-0" />
              {item.label}
            </NavLink>
          ))}
        </nav>
        <Who name={staff.full_name || staff.phone} role={staff.role} onSignOut={signOut} />
      </aside>

      {/* --------------------------------------------------------- the phone bar */}
      <header className="no-print flex items-center justify-between border-b bg-rail px-4 py-3 text-rail-ink md:hidden">
        <Brand compact />
        <button
          type="button"
          onClick={() => setOpen((was) => !was)}
          aria-label="Menyu"
          className="rounded-control p-2 hover:bg-white/10"
        >
          {open ? <X className="size-5" /> : <Menu className="size-5" />}
        </button>
      </header>

      {open ? (
        <nav className="no-print grid gap-1 border-b bg-rail px-3 pb-3 text-rail-ink md:hidden">
          {items.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              onClick={() => setOpen(false)}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-control px-3 text-body",
                  "h-control-lg hover:bg-white/10",
                  isActive && "bg-brand text-brand-ink",
                )
              }
            >
              <item.icon className="size-5 shrink-0" />
              {item.label}
            </NavLink>
          ))}
          <Button
            variant="ghost"
            onClick={signOut}
            className="h-control-lg justify-start gap-3 px-3 text-rail-ink hover:bg-white/10"
          >
            <LogOut className="size-5" />
            Chiqish
          </Button>
        </nav>
      ) : null}

      <main className="min-w-0 flex-1 bg-canvas">
        <div className="mx-auto w-full max-w-6xl p-(--gap-page)">
          <Outlet />
        </div>
      </main>
    </div>
  )
}

function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <div className={cn("flex items-center gap-2 px-4", compact ? "" : "py-4")}>
      <span className="grid size-7 place-items-center rounded-control bg-brand text-brand-ink">
        MB
      </span>
      <span className="font-semibold tracking-tight">Mini Bozor</span>
    </div>
  )
}

function Who({
  name,
  role,
  onSignOut,
}: {
  name: string
  role: string
  onSignOut: () => void
}) {
  return (
    <div className="border-t border-white/10 p-3">
      <div className="px-1 pb-2">
        <div className="truncate text-small">{name}</div>
        <div className="text-micro opacity-70">{roleWord(role)}</div>
      </div>
      <Button
        variant="ghost"
        onClick={onSignOut}
        className="h-control w-full justify-start gap-2 px-1 text-rail-ink hover:bg-white/10"
      >
        <LogOut className="size-4" />
        Chiqish
      </Button>
    </div>
  )
}

function roleWord(role: string): string {
  if (role === "admin") return "Administrator"
  if (role === "warehouse") return "Ombor xodimi"
  if (role === "courier") return "Kuryer"
  return role
}
