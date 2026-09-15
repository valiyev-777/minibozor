/**
 * The courier's own shell — and the decision behind it.
 *
 * ------------------------------------------------------------ why a second one
 *
 * `components/shell.tsx` is the building's chrome: a 264px rail down the left,
 * a 72px top bar with a breadcrumb in it, a `PageHeader` card at the top of
 * every screen, and `p-6` of grey canvas around a column of panels. It is
 * good, three roles use it, and **none of it applies here**.
 *
 * The courier's design is a full-bleed map with frosted glass floating on top
 * and a tab bar of its own hovering above the home indicator. There is no
 * canvas to pad, no page to put a header card on, and a breadcrumb for a
 * four-screen app is a label. Squeezing this into the back office's shell
 * would mean a screen whose first act is to undo the padding, cancel the
 * background, hide the top bar and draw a second navigation under the first
 * one — which is not reuse, it is two shells fighting.
 *
 * So the courier role gets its own, and the other roles' shell is not touched.
 * The two are siblings in `App.tsx` rather than one wrapping the other,
 * because the moment one is inside the other the rail's `<main>` padding and
 * the phone's `--bottom-nav` are in play again.
 *
 * What is **shared** is everything that should be: the session, the query
 * client, the theme class on `<html>`, the toaster, `lib/format`, and every
 * token in `shared/theme.css`. Two visual languages, one system.
 *
 * ------------------------------------------------------------------- the shape
 *
 * Fixed to the viewport and `overflow-hidden`, because the screens inside it
 * scroll *themselves*: a bottom sheet that scrolls its own stop list while the
 * map behind it stays put is not something a document-scrolling page can do.
 * That also means the tab bar is simply positioned rather than `fixed`, and
 * `--bottom-nav` — which is the desk shell's answer to the same problem — is
 * not in use here at all. Each screen reads `--kuryer-tabs` instead.
 *
 * **The bar is the top of the stack.** `z-[900]`, above every sheet and every
 * floating pill a screen draws: a bottom sheet that slides over the app's own
 * navigation is a sheet with no way out of it, and that is exactly what
 * happened when the sheet and the bar were both in the five hundreds.
 * `components/kuryer/map` isolates Leaflet's own panes, so its internal
 * 200–800 never enters this argument.
 *
 * Always `density-comfortable`, at every width. The desk shell gives a role
 * its density and then overrides it on a phone; here there is nothing to
 * decide. These screens are a phone app, and at a desk they are the same phone
 * app in a column — which is what the owner sees when they open it to check
 * something, and is better than a courier app stretched across 1400px.
 */

import { Banknote, Route, User, Warehouse } from "lucide-react"
import { createContext, useContext, useMemo, useState } from "react"
import { NavLink, Outlet, useLocation } from "react-router-dom"

import { ScreenBoundary } from "@/pages/oops"
import { cn } from "@/lib/cn"
import { useSession } from "@/lib/session"

/* ------------------------------------------------------------------ the draft
 *
 * A delivery is three screens — the stop, the proof, the money — and one write
 * at the end of them. What the courier typed on the way has to survive the
 * navigation between them, and it must not survive a change of order: taking
 * the photo for door 4 and then opening door 5 has to start clean, or the
 * wrong doorstep is filed against the wrong delivery.
 *
 * In memory and nowhere else. This is not worth `localStorage`: a courier who
 * closes the app between "I photographed the door" and "I took the money" has
 * not delivered anything, and a stale recipient name resurrected an hour later
 * is worse than an empty field. The one write that matters is keyed and
 * queued by `api()`; this is only the form in front of it.
 */
export type Draft = {
  orderId: number
  recipientName: string
  /** A media path from `POST /media`, or "" — the server takes either. */
  photoUrl: string
  /** Who took it, as the design's three answers. Kept because it prefixes the
   *  name that is actually recorded. */
  who: number
  /** What the customer handed over, for the change sum. Never sent: the
   *  server is told the amount *owed* and refuses anything else. */
  given: string
}

type DraftState = {
  draft: Draft | null
  /** Starts a draft for this order, or leaves the one already in progress
   *  alone. Called from an effect as a screen opens, so it must be idempotent
   *  — a second call for the same order must not wipe the photograph. */
  open: (orderId: number, recipientName: string) => void
  set: (patch: Partial<Draft>) => void
  clear: () => void
}

const DraftContext = createContext<DraftState | null>(null)

export function useDraft(): DraftState {
  const held = useContext(DraftContext)
  if (!held) throw new Error("useDraft outside the courier shell")
  return held
}

/* -------------------------------------------------------------------- the tabs
 *
 * Four, and they are the four the design names: the warehouse you load at, the
 * round you drive, what you have earned, and you. `covers` is every route a tab
 * stands for, so the stop, the proof and the payment screens all keep
 * `Marshrut` lit rather than lighting nothing — the same rule the desk shell's
 * `BarSlot` follows, for the same reason.
 */
const TABS = [
  { to: "/kuryer", label: "Ombor", icon: Warehouse, covers: ["/kuryer", "/kuryer/olish"] },
  { to: "/kuryer/marshrut", label: "Marshrut", icon: Route, covers: ["/kuryer/marshrut"] },
  { to: "/kuryer/daromad", label: "Daromad", icon: Banknote, covers: ["/kuryer/daromad"] },
  { to: "/kuryer/profil", label: "Profil", icon: User, covers: ["/kuryer/profil"] },
]

export function KuryerShell() {
  const { staff } = useSession()
  const location = useLocation()
  const [draft, setDraft] = useState<Draft | null>(null)

  const drafting = useMemo<DraftState>(
    () => ({
      draft,
      open(orderId, recipientName) {
        // A draft belongs to one order. Arriving at a different door starts
        // again rather than inheriting the last one's photograph.
        setDraft((was) =>
          was && was.orderId === orderId
            ? was
            : { orderId, recipientName, photoUrl: "", who: 0, given: "" },
        )
      },
      set(patch) {
        setDraft((was) => (was ? { ...was, ...patch } : was))
      },
      clear() {
        setDraft(null)
      },
    }),
    [draft],
  )

  if (!staff) return null

  return (
    <DraftContext.Provider value={drafting}>
      {/* `fixed inset-0` rather than `min-h-full`: these screens own the
          viewport and scroll inside themselves. `no-select` because
          long-pressing a stop while holding a phone against a parcel puts a
          selection handle over the button somebody was reaching for. */}
      <div className="density-comfortable no-select fixed inset-0 flex flex-col overflow-hidden bg-kuryer-ground text-kuryer-ink">
        <div className="relative min-h-0 flex-1">
          <ScreenBoundary home="/kuryer" at={location.pathname}>
            <Outlet />
          </ScreenBoundary>
        </div>
        <TabBar at={location.pathname} />
      </div>
    </DraftContext.Provider>
  )
}

/**
 * The bar of four, floating clear of the bottom edge rather than sitting on
 * it.
 *
 * The desk shell's phone bar is a band flush to the window, which is right for
 * a screen made of stacked cards. This one hovers over a map that continues
 * underneath it, so it is a pane of the same glass as everything else, inset
 * from three edges, with the home indicator's own space left under it.
 *
 * The label is always printed. An icon-only bar is a quiz, and `Ombor` and
 * `Marshrut` are not guessable from a warehouse and an arrow.
 */
function TabBar({ at }: { at: string }) {
  // Longest matching cover wins, so `/kuryer/marshrut/12/tolov` lights
  // Marshrut and not Ombor — `/kuryer` is a prefix of every route in here.
  const active = useMemo(() => {
    let best: string | undefined
    let longest = -1
    for (const tab of TABS) {
      for (const cover of tab.covers) {
        const hit = at === cover || at.startsWith(`${cover}/`)
        if (hit && cover.length > longest) {
          longest = cover.length
          best = tab.to
        }
      }
    }
    return best
  }, [at])

  return (
    <nav
      aria-label="Kuryer menyusi"
      className="pointer-events-none absolute inset-x-3 bottom-0 z-[900] pb-[max(0.75rem,env(safe-area-inset-bottom))]"
    >
      <div className="kuryer-glass pointer-events-auto flex overflow-hidden rounded-slab shadow-kuryer-float">
        {TABS.map((tab) => {
          const on = tab.to === active
          return (
            <NavLink
              key={tab.to}
              to={tab.to}
              aria-current={on ? "page" : undefined}
              className={cn(
                "flex h-control-md min-w-0 flex-1 flex-col items-center justify-center gap-0.5 transition-colors",
                on ? "text-kuryer-act" : "text-kuryer-ink-soft",
              )}
            >
              <tab.icon className="size-5 shrink-0" />
              <span className="w-full truncate px-1 text-center text-micro font-semibold">
                {tab.label}
              </span>
            </NavLink>
          )
        })}
      </div>
    </nav>
  )
}
