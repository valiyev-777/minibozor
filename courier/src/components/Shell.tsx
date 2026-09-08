import * as React from "react"
import { NavLink, Outlet } from "react-router-dom"
import { Download, Package, PackageSearch, Truck, User, WifiOff } from "lucide-react"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/api/client"
import type { Stop } from "@/api/types"
import { Button } from "@/ui/button"
import { cn } from "@/ui/cn"
import { useCourier, useSession } from "@/auth/session"
import { t } from "@/lib/labels"

/**
 * The frame: a header, three destinations, and one content column.
 *
 * There used to be no navigation at all, because there was nowhere to go — a
 * courier was handed a round and read it. They choose their own work now, so
 * there are three places to be: the board of orders nobody has taken, the
 * ones they took, and what it has all come to. That is a real menu.
 *
 * **The menu is a bottom bar on a phone and a rail on a laptop.** Both, from
 * one list, because this app is genuinely used on both: a courier's phone at
 * a door, and a screen in the warehouse where somebody watches the board. A
 * bottom bar is where a thumb is; a bottom bar on a 27-inch monitor is a
 * stripe of buttons a mile from the content. The breakpoint is `lg`, and
 * below it the bar sits above the home indicator (`pb-safe`).
 *
 * The content column is capped and centred. Unbounded, a row of a stop's
 * address stretches to 2000px and the eye loses the line it is on; the app
 * would read as a phone screen someone dragged wider.
 */
const LINKS = [
  { to: "/board", label: t.board, icon: PackageSearch, badge: "board" },
  { to: "/", label: t.myWork, icon: Truck, badge: "mine" },
  { to: "/profile", label: t.profile, icon: User, badge: null },
] as const

export function Shell() {
  const session = useSession()
  const courier = useCourier()
  const online = useOnline()
  const install = useInstall()

  // Two counts, and they are the reason a courier opens the app: is there
  // anything to take, and how much have I still got on me. Cheap enough to
  // keep fresh — a courier who has to open a tab to find out whether the
  // board has anything on it will stop looking.
  const board = useQuery({
    queryKey: ["board"],
    queryFn: () => api<Stop[]>("/courier/orders/available"),
    refetchInterval: 30_000,
  })
  const mine = useQuery({
    queryKey: ["round"],
    queryFn: () => api<Stop[]>("/courier/orders"),
    refetchInterval: 60_000,
  })
  const counts: Record<string, number> = {
    board: board.data?.length ?? 0,
    mine: mine.data?.length ?? 0,
  }

  return (
    <div className="flex min-h-full flex-col lg:flex-row">
      {/* The rail, on a laptop only. Same list, same order, same counts. */}
      <aside className="hidden shrink-0 border-r border-line bg-surface lg:sticky lg:top-0 lg:flex lg:h-screen lg:w-60 lg:flex-col">
        <div className="flex items-center gap-3 px-4 py-4">
          <span className="inline-flex size-9 shrink-0 items-center justify-center rounded-[var(--radius-control)] bg-brand-soft text-brand-deep">
            <Package className="size-5" />
          </span>
          <div className="min-w-0">
            <p className="truncate font-semibold text-ink">{t.app}</p>
            <p className="truncate text-[length:var(--text-micro)] text-ink-soft">
              {courier.full_name || courier.phone}
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
        <div className="space-y-2 p-3">
          {install ? (
            <Button className="w-full" size="sm" onClick={install}>
              <Download />
              {t.install}
            </Button>
          ) : null}
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
        {/* On a phone this is the whole chrome; on a laptop the rail has the
            name and the buttons, so the header keeps only what is urgent. */}
        <header className="sticky top-0 z-20 border-b border-line bg-surface/95 backdrop-blur lg:static lg:border-b-0 lg:bg-transparent">
          <div className="flex items-center gap-3 px-[var(--gap-page)] py-3 lg:hidden">
            <span className="inline-flex size-9 shrink-0 items-center justify-center rounded-[var(--radius-control)] bg-brand-soft text-brand-deep">
              <Package className="size-5" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate font-semibold text-ink">{t.app}</p>
              <p className="truncate text-[length:var(--text-micro)] text-ink-soft">
                {courier.full_name || courier.phone}
              </p>
            </div>
            {install ? (
              <Button size="sm" onClick={install}>
                <Download />
                {t.install}
              </Button>
            ) : null}
            <Button variant="ghost" size="sm" onClick={() => void session.signOut()}>
              {t.signOut}
            </Button>
          </div>

          {/* Said out loud, because there is no outbox in this version: a
              write that cannot reach the server fails, and a courier who
              knows the phone is offline will not spend five minutes
              wondering why the button does nothing. */}
          {online ? null : (
            <p
              role="status"
              className="flex items-center gap-2 bg-warn-soft px-[var(--gap-page)] py-2
                         text-[length:var(--text-small)] font-medium text-warn-ink"
            >
              <WifiOff className="size-4 shrink-0" />
              Internet yo'q — yozib bo'lmaydi. Signal qaytganda qayta bosing.
            </p>
          )}
        </header>

        <main className="flex-1 pb-28 lg:pb-8 lg:pt-6">
          <div className="mx-auto w-full max-w-3xl">
            <Outlet />
          </div>
        </main>
      </div>

      {/* The bar, on a phone only. Fixed rather than sticky: a courier
          scrolling a long board should never have to scroll back to move. */}
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

/**
 * One destination, in both shapes.
 *
 * `end` on the round because its path is `/`, which is a prefix of every
 * other route and would otherwise light up on all of them.
 */
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
      end={link.to === "/"}
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
        {/* Nought is an absent badge, not a zero: a number that is always on
            is a number nobody reads. */}
        {count > 0 ? (
          <span
            className="absolute -right-2 -top-1.5 inline-flex min-w-4 justify-center rounded-full
                       bg-brand px-1 text-[11px] font-semibold leading-4 text-brand-ink
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

/** Whether the phone thinks it has a network, which is the best we can know. */
function useOnline(): boolean {
  const [online, setOnline] = React.useState(
    typeof navigator === "undefined" ? true : navigator.onLine,
  )
  React.useEffect(() => {
    const up = () => setOnline(true)
    const down = () => setOnline(false)
    window.addEventListener("online", up)
    window.addEventListener("offline", down)
    return () => {
      window.removeEventListener("online", up)
      window.removeEventListener("offline", down)
    }
  }, [])
  return online
}

/**
 * The install button, and only when the browser has offered one.
 *
 * `beforeinstallprompt` fires once, before the page can ask for it, so the
 * event is captured and held — calling `prompt()` later is what turns a
 * button press into the browser's own dialogue. A browser that never fires it
 * (every iOS one) gets no button rather than a button that does nothing:
 * there, installing is "Share → Add to Home Screen" and a button we render
 * cannot reach it.
 */
type InstallEvent = Event & { prompt: () => Promise<void> }

function useInstall(): (() => void) | null {
  const [event, setEvent] = React.useState<InstallEvent | null>(null)

  React.useEffect(() => {
    const capture = (raw: Event) => {
      raw.preventDefault()
      setEvent(raw as InstallEvent)
    }
    window.addEventListener("beforeinstallprompt", capture)
    // Once it is installed the button is noise, so it goes.
    const installed = () => setEvent(null)
    window.addEventListener("appinstalled", installed)
    return () => {
      window.removeEventListener("beforeinstallprompt", capture)
      window.removeEventListener("appinstalled", installed)
    }
  }, [])

  if (!event) return null
  return () => {
    void event.prompt()
    setEvent(null)
  }
}
