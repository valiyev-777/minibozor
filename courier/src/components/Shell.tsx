import { NavLink, Outlet } from "react-router-dom"
import { CloudOff, Inbox, PackageCheck, RotateCcw, Truck } from "lucide-react"
import clsx from "clsx"
import { useOffline } from "@/offline/OfflineProvider"
import { useSession } from "@/auth/session"

/**
 * The frame: a status strip at the top, four destinations at the bottom.
 *
 * The strip is the honest part. It says whether the phone can reach the server
 * and how many actions are waiting, on every screen, all the time. A courier
 * who does not know they are offline is a courier who walks away from a round
 * with the day's work in a queue nobody has seen.
 */
export function Shell() {
  const { reachable, syncing, unsent } = useOffline()
  const session = useSession()
  const offlineSession = session.status === "offline"

  const waiting = unsent.pending
  const blocked = unsent.blocked
  const bad = !reachable || offlineSession

  return (
    <div className="flex h-full flex-col">
      <header
        className={clsx(
          "flex items-center justify-between gap-3 border-b-2 px-4 py-2",
          bad ? "border-pending bg-pending-fill text-pending" : "border-line text-muted",
        )}
      >
        <span className="flex items-center gap-2 text-base font-semibold">
          {bad ? <CloudOff className="size-5" /> : <Truck className="size-5" />}
          {bad ? "Tarmoq yo'q" : syncing ? "Yuborilmoqda…" : "Tarmoq bor"}
        </span>
        {waiting > 0 || blocked > 0 ? (
          <NavLink
            to="/outbox"
            className="rounded-lg bg-pending px-2.5 py-1 text-sm font-bold text-page"
          >
            {blocked > 0
              ? `Yuborilmagan ${waiting} · ${blocked} xato`
              : `Yuborilmagan ${waiting}`}
          </NavLink>
        ) : null}
      </header>

      <main className="min-h-0 flex-1 overflow-y-auto">
        <Outlet />
      </main>

      <nav className="grid grid-cols-4 border-t-2 border-line pb-safe">
        <Tab to="/" icon={<Truck className="size-7" />} label="Reys" />
        <Tab to="/shift" icon={<PackageCheck className="size-7" />} label="Smena" />
        <Tab to="/pickups" icon={<RotateCcw className="size-7" />} label="Yig'uv" />
        <Tab
          to="/outbox"
          icon={<Inbox className="size-7" />}
          label="Navbat"
          badge={waiting + blocked}
        />
      </nav>
    </div>
  )
}

function Tab({
  to,
  icon,
  label,
  badge,
}: {
  to: string
  icon: React.ReactNode
  label: string
  badge?: number
}) {
  return (
    <NavLink
      to={to}
      end={to === "/"}
      className={({ isActive }) =>
        clsx(
          "relative flex h-16 flex-col items-center justify-center gap-0.5 text-sm font-semibold",
          isActive ? "text-brand" : "text-muted",
        )
      }
    >
      {icon}
      {label}
      {badge ? (
        <span className="absolute top-1.5 right-[22%] min-w-5 rounded-full bg-pending px-1 text-xs font-bold text-page">
          {badge}
        </span>
      ) : null}
    </NavLink>
  )
}
