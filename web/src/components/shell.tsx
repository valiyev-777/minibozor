/**
 * The frame every screen sits in.
 *
 * A near-black rail down the left and a white bar across the top — the shape
 * every back office in this building has, so somebody who works in two of
 * them is not learning a second building. On a phone the rail becomes a
 * sheet behind a button, because half the people using this are standing up
 * holding something and a 264px column is most of their screen.
 *
 * ------------------------------------------------------------------ the rail
 *
 * As tall as the **window**, not as tall as the page.
 *
 * It was a plain flex child once, so it stretched to whatever the screen
 * beside it happened to be: the shelf map made it two thousand pixels of dark
 * blue. It is `fixed` now, and the item list scrolls inside itself on a short
 * window rather than pushing anything off the end.
 *
 * It collapses to icons, and it re-expands while the pointer is over it. The
 * collapse is for the shelf map, which is a wide drawing and wants the
 * column back; the hover is so that collapsing does not mean *losing* the
 * menu — a rail you have to un-collapse to read is a rail nobody collapses.
 *
 * ------------------------------------------------------------------ the item
 *
 * **Full-bleed bars, not pills.** A menu item touches both edges of the rail
 * and has no radius, which is the single most visible thing about the house
 * chrome and the thing ours was getting wrong: an 8px pill inside 12px of
 * padding turns the column into a stack of floating tablets and the rail
 * into a background they happen to be on. A bar that reaches the edge reads
 * as part of the rail, which is what it is. There is no left accent stripe
 * either — the fill is the answer, and a stripe as well is two devices
 * saying one thing.
 *
 * ------------------------------------------------------------------ who
 *
 * The signed-in person is **not** down here. They are in the top bar, in the
 * menu that also holds sign-out and the theme — one place where a person's
 * own things live, rather than a name at the foot of the rail and the
 * controls for it eight hundred pixels away at the top right.
 */

import {
  ChevronDown,
  ChevronLeft,
  LogOut,
  Menu,
  Monitor,
  Moon,
  Palette,
  Sun,
  X,
} from "lucide-react"
import { useEffect, useMemo, useState } from "react"
import { NavLink, Outlet, useLocation } from "react-router-dom"

import { RailSearch } from "@/components/rail-search"
import {
  DropdownMenu,
  DropdownMenuCheckItem,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { cn } from "@/lib/cn"
import { densityFor, isGroup, matchNav, navFor, type NavItem } from "@/lib/nav"
import { useDashboard } from "@/lib/queries"
import { useSession } from "@/lib/session"
import { useTheme, type ThemeMode } from "@/lib/theme"

const RAIL_OPEN = "16.5rem" /* 264px */
const RAIL_SHUT = "4.75rem" /* 76px — an icon and its padding */

export function Shell() {
  const { staff } = useSession()
  const [pinned, setPinned] = useState(() => localStorage.getItem("mb:rail") !== "shut")
  const [hovered, setHovered] = useState(false)
  const [sheet, setSheet] = useState(false)
  const location = useLocation()

  // A menu that stays open behind the screen it opened is a menu that hides
  // the screen it opened.
  useEffect(() => setSheet(false), [location.pathname])

  const items = useMemo(() => (staff ? navFor(staff.role) : []), [staff])
  const here = useMemo(
    () => matchNav(items, location.pathname),
    [items, location.pathname],
  )

  // Exactly one drawer open, and which one is a fact about the URL rather
  // than about what somebody clicked ten screens ago. Recomputed on every
  // navigation; opened by hand in between.
  const parentKey = here?.parent?.to ?? null
  const [openKey, setOpenKey] = useState<string | null>(parentKey)
  useEffect(() => setOpenKey(parentKey), [location.pathname, parentKey])

  if (!staff) return null

  const open = pinned || hovered

  const toggle = () => {
    setHovered(false)
    setPinned((was) => {
      localStorage.setItem("mb:rail", was ? "shut" : "open")
      return !was
    })
  }

  const expand = () => {
    if (pinned) return
    localStorage.setItem("mb:rail", "open")
    setPinned(true)
  }

  return (
    <div className={cn("min-h-full", densityFor(staff.role))}>
      {/* ----------------------------------------------------------- the rail */}
      <aside
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        style={{ width: open ? RAIL_OPEN : RAIL_SHUT }}
        className="no-print fixed inset-y-0 left-0 z-40 hidden flex-col bg-rail text-rail-ink transition-[width] duration-200 md:flex"
      >
        <Brand open={open} onToggle={toggle} pinned={pinned} />
        <RailSearch items={items} collapsed={!open} onExpand={expand} />
        <nav
          aria-label="Asosiy menyu"
          className="scroll-slim flex-1 overflow-y-auto overflow-x-hidden pb-3"
        >
          {items.map((item) => (
            <RailRow
              key={item.to}
              item={item}
              open={open}
              activeTo={here?.item.to}
              openKey={openKey}
              onOpenKey={setOpenKey}
              onExpand={expand}
            />
          ))}
        </nav>
      </aside>

      {/* The rail is `fixed`, so the page needs to be told how wide it is. A
       * margin rather than a flex sibling: the shelf map is a wide drawing
       * that sets its own scroll container, and a flex row would have it
       * fighting the rail for the width every time it redrew. */}
      <div
        style={{ marginInlineStart: pinned ? RAIL_OPEN : RAIL_SHUT }}
        className="min-w-0 transition-[margin] duration-200 max-md:!ms-0">
        <TopBar
          trail={here}
          name={staff.full_name || staff.phone}
          role={staff.role}
          onOpenSheet={() => setSheet((was) => !was)}
          sheetOpen={sheet}
        />

        {/* ------------------------------------------------------- the sheet */}
        {sheet ? (
          <nav
            aria-label="Asosiy menyu"
            className="no-print border-b border-line bg-rail py-2 text-rail-ink md:hidden"
          >
            {items.map((item) => (
              <RailRow
                key={item.to}
                item={item}
                open
                large
                activeTo={here?.item.to}
                openKey={openKey}
                onOpenKey={setOpenKey}
                onExpand={expand}
              />
            ))}
          </nav>
        ) : null}

        <main className="p-(--gap-page)">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ the rail */

/** The shape every row in the rail has: 44px, full-bleed, square. */
const ROW =
  "group relative flex w-full items-center gap-3 px-4 text-left transition-colors"

function RailRow({
  item,
  open,
  large,
  activeTo,
  openKey,
  onOpenKey,
  onExpand,
}: {
  item: NavItem
  open: boolean
  large?: boolean
  activeTo?: string
  openKey: string | null
  onOpenKey: (key: string | null) => void
  onExpand: () => void
}) {
  if (isGroup(item)) {
    return (
      <RailGroup
        item={item}
        open={open}
        large={large}
        activeTo={activeTo}
        openKey={openKey}
        onOpenKey={onOpenKey}
        onExpand={onExpand}
      />
    )
  }
  return <RailLink item={item} open={open} large={large} />
}

function RailLink({
  item,
  open,
  large = false,
}: {
  item: NavItem
  open: boolean
  large?: boolean
}) {
  return (
    <NavLink
      to={item.to}
      end={item.to === "/"}
      title={open ? undefined : item.label}
      className={({ isActive }) =>
        cn(
          ROW,
          "h-control-lg font-medium",
          large ? "text-body" : "text-small",
          open ? "" : "justify-center px-0",
          isActive
            ? "bg-brand/15 text-white"
            : "text-rail-ink hover:bg-brand/8 hover:text-brand",
        )
      }
    >
      {({ isActive }) => (
        <>
          {item.icon ? (
            <item.icon
              className={cn(
                "size-5 shrink-0 transition-colors",
                isActive ? "text-brand" : "text-rail-ink group-hover:text-brand",
              )}
            />
          ) : null}
          {open ? (
            <>
              <span className="flex-1 truncate">{item.label}</span>
              <Count of={item.badge} />
            </>
          ) : (
            <Count of={item.badge} dot />
          )}
        </>
      )}
    </NavLink>
  )
}

/**
 * A drawer: a row that opens rather than goes anywhere, and the screens
 * inside it.
 *
 * A child has no icon of its own. It gets a dash — the width of a
 * hyphen, two pixels tall — which is not decoration: a column of six icons
 * where two of them belong *under* another one reads as eight equal things,
 * and the dash is what says "this one is filed inside that one" without
 * spending an icon on it.
 */
function RailGroup({
  item,
  open,
  large = false,
  activeTo,
  openKey,
  onOpenKey,
  onExpand,
}: {
  item: NavItem
  open: boolean
  large?: boolean
  activeTo?: string
  openKey: string | null
  onOpenKey: (key: string | null) => void
  onExpand: () => void
}) {
  const children = item.children ?? []
  const holdsActive = children.some((child) => child.to === activeTo)
  const isOpen = openKey === item.to

  return (
    <div>
      <button
        type="button"
        aria-expanded={isOpen}
        title={open ? undefined : item.label}
        onClick={() => {
          // On a narrow rail there is nowhere to put the children, so the
          // click widens the rail first rather than opening a drawer the
          // person cannot see.
          if (!open) onExpand()
          onOpenKey(isOpen ? null : item.to)
        }}
        className={cn(
          ROW,
          "h-control-lg font-medium",
          large ? "text-body" : "text-small",
          open ? "" : "justify-center px-0",
          // While the drawer is open the fill belongs to the child that is
          // selected, not to the drawer as well — two fills stacked read as
          // two selections. A shut rail has no children to show, so the
          // drawer carries the fill itself.
          holdsActive && (!open || !isOpen)
            ? "bg-brand/15 text-white"
            : "text-rail-ink hover:bg-brand/8 hover:text-brand",
        )}
      >
        {item.icon ? (
          <item.icon
            className={cn(
              "size-5 shrink-0 transition-colors",
              holdsActive ? "text-brand" : "text-rail-ink group-hover:text-brand",
            )}
          />
        ) : null}
        {open ? (
          <>
            <span className={cn("flex-1 truncate", holdsActive && "text-white")}>
              {item.label}
            </span>
            <ChevronDown
              className={cn(
                "size-4 shrink-0 text-rail-ink/45 transition-transform duration-200",
                isOpen && "rotate-180",
              )}
            />
          </>
        ) : null}
      </button>

      {/* Height animated with a grid track rather than a max-height guess:
       * a guessed maximum is either a jump or a lag, depending on how many
       * children the drawer turns out to have. */}
      <div
        className={cn(
          "grid transition-[grid-template-rows] duration-200 ease-out",
          open && isOpen ? "grid-rows-[1fr]" : "grid-rows-[0fr]",
        )}
      >
        <div className="overflow-hidden">
          {children.map((child) => (
            <NavLink
              key={child.to}
              to={child.to}
              tabIndex={open && isOpen ? undefined : -1}
              aria-hidden={open && isOpen ? undefined : true}
              className={({ isActive }) =>
                cn(
                  ROW,
                  "h-control-lg gap-2 ps-8 font-normal",
                  large ? "text-body" : "text-small",
                  isActive
                    ? "bg-brand/15 text-white"
                    : "text-rail-ink/60 hover:bg-brand/8 hover:text-white",
                )
              }
            >
              {({ isActive }) => (
                <>
                  <span
                    aria-hidden
                    className={cn(
                      "h-[2px] w-3 shrink-0 transition-colors",
                      isActive ? "bg-white" : "bg-rail-ink/40 group-hover:bg-white",
                    )}
                  />
                  <span className="flex-1 truncate">{child.label}</span>
                  <Count of={child.badge} />
                </>
              )}
            </NavLink>
          ))}
        </div>
      </div>
    </div>
  )
}

/**
 * The number beside a menu item, from the dashboard tile of the same key.
 *
 * A queue nobody can see the length of is a queue that grows. "Sotuvga
 * chiqarish" holds goods that are on a shelf and unsellable, which breaks
 * nothing and errors nowhere — so the only thing that makes it get worked is
 * a figure somebody walks past.
 *
 * On a collapsed rail there is no room for the figure, and a queue that
 * disappears when the rail narrows is the same queue nobody can see. It
 * becomes a dot in the corner of the icon instead: less information, but the
 * one bit that matters — there is something in there.
 */
function Count({ of, dot = false }: { of?: string; dot?: boolean }) {
  // Called unconditionally because a hook must be, and switched off when
  // there is no badge to draw: a courier may not read the dashboard at all.
  const dashboard = useDashboard(Boolean(of))
  if (!of) return null
  const tile = dashboard.data?.tiles.find((one) => one.key === of)
  if (!tile?.value) return null

  if (dot) {
    return (
      <span
        aria-hidden
        className={cn(
          "absolute right-3 top-2 size-2 rounded-full ring-2 ring-rail",
          tile.urgent ? "bg-danger" : "bg-brand",
        )}
      />
    )
  }
  return (
    <span
      className={cn(
        "min-w-5 rounded-full px-1.5 text-center text-micro font-semibold tabular",
        tile.urgent ? "bg-danger text-danger-ink" : "bg-white/15 text-white",
      )}
    >
      {tile.value}
    </span>
  )
}

/**
 * The rail's head: the mark, the name, and the button that narrows it.
 *
 * The blue behind it is a heavily blurred wash of the accent rather than a
 * flat panel — the top of the rail is where the eye lands first, and a
 * near-black column with nothing at the top of it reads as an unfinished
 * page. It is `pointer-events-none` because it is a light, not a surface.
 */
function Brand({
  open,
  pinned,
  onToggle,
}: {
  open: boolean
  pinned: boolean
  onToggle: () => void
}) {
  return (
    <div className="relative flex h-[72px] shrink-0 items-center gap-3 overflow-hidden border-b border-white/10 px-4">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-brand opacity-60 blur-[70px]"
      />
      <span className="relative z-10 grid size-9 shrink-0 place-items-center rounded-control bg-brand text-body font-bold text-brand-ink">
        MB
      </span>
      {open ? (
        <span className="relative z-10 flex-1 truncate font-semibold tracking-tight text-white">
          Mini Bozor
        </span>
      ) : null}
      {open ? (
        <button
          type="button"
          onClick={onToggle}
          aria-label={pinned ? "Menyuni yig'ish" : "Menyuni ochish"}
          className="relative z-10 grid size-7 place-items-center rounded-control text-white/70 transition-colors hover:bg-white/10 hover:text-white"
        >
          <ChevronLeft
            className={cn("size-4 transition-transform", !pinned && "rotate-180")}
          />
        </button>
      ) : null}
    </div>
  )
}

/* ---------------------------------------------------------------- the top bar */

/**
 * Breadcrumb on the left, the person on the right, and a hairline shadow
 * that only appears once the page has scrolled — so a screen at rest is flat
 * and a screen with content above the fold says so.
 *
 * The separator is a brand dot rather than a slash. A slash between two
 * words is a third word; a 4px dot in the accent is punctuation, and it
 * ties the one coloured thing in the top bar to the one coloured thing in
 * the rail.
 */
function TopBar({
  trail,
  name,
  role,
  onOpenSheet,
  sheetOpen,
}: {
  trail: { item: NavItem; parent?: NavItem } | undefined
  name: string
  role: string
  onOpenSheet: () => void
  sheetOpen: boolean
}) {
  const [scrolled, setScrolled] = useState(false)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 0)
    onScroll()
    window.addEventListener("scroll", onScroll, { passive: true })
    return () => window.removeEventListener("scroll", onScroll)
  }, [])

  // A drawer whose first screen carries the drawer's own name — Buyurtmalar
  // inside Buyurtmalar — says it twice and means it once. The parent is the
  // location and the leaf is the page; where they are the same word there is
  // only one of them to print.
  const crumbs = ["Mini Bozor"]
  if (trail?.parent && trail.parent.label !== trail.item.label) {
    crumbs.push(trail.parent.label)
  }
  if (trail) crumbs.push(trail.item.label)

  return (
    <header
      className={cn(
        "no-print sticky top-0 z-30 flex h-[72px] items-center justify-between gap-4 bg-surface px-4 transition-shadow md:px-6",
        scrolled ? "shadow-raised" : "",
      )}
    >
      <div className="flex min-w-0 items-center gap-3">
        <button
          type="button"
          onClick={onOpenSheet}
          aria-label="Menyu"
          className="grid size-control place-items-center rounded-control text-ink-soft hover:bg-line-soft md:hidden"
        >
          {sheetOpen ? <X className="size-5" /> : <Menu className="size-5" />}
        </button>
        <nav
          aria-label="Joylashuv"
          className="flex min-w-0 items-center gap-2 truncate text-small"
        >
          {crumbs.map((crumb, at) => (
            <span key={at} className="flex min-w-0 items-center gap-2">
              {at > 0 ? (
                <span aria-hidden className="size-1 shrink-0 rounded-full bg-brand" />
              ) : null}
              <span
                className={cn(
                  "truncate",
                  at === crumbs.length - 1
                    ? "text-ink-faint"
                    : "font-medium text-ink",
                )}
              >
                {crumb}
              </span>
            </span>
          ))}
        </nav>
      </div>

      <ProfileMenu name={name} role={role} />
    </header>
  )
}

/** Who is signed in, and everything that belongs to them: the theme, and the
 *  way out. */
function ProfileMenu({ name, role }: { name: string; role: string }) {
  const { signOut } = useSession()
  const { mode, setMode } = useTheme()

  const themes: Array<{ key: ThemeMode; label: string; icon: typeof Sun }> = [
    { key: "light", label: "Yorug'", icon: Sun },
    { key: "dark", label: "Qorong'i", icon: Moon },
    { key: "system", label: "Tizim bo'yicha", icon: Monitor },
  ]

  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="flex h-control items-center gap-2.5 rounded-control px-2 text-left outline-none transition-colors hover:bg-line-soft focus-visible:ring-2 focus-visible:ring-brand/40">
        <span className="grid size-8 shrink-0 place-items-center rounded-full bg-brand-soft text-micro font-semibold text-brand-deep">
          {initials(name)}
        </span>
        <span className="hidden min-w-0 sm:block">
          <span className="block max-w-40 truncate text-small font-medium">{name}</span>
          <span className="block text-micro text-ink-faint">{roleWord(role)}</span>
        </span>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="end">
        <DropdownMenuLabel>{name}</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuSub>
          <DropdownMenuSubTrigger>
            <Palette />
            Ko'rinish
          </DropdownMenuSubTrigger>
          <DropdownMenuSubContent>
            {themes.map((one) => (
              <DropdownMenuCheckItem
                key={one.key}
                checked={mode === one.key}
                onSelect={() => setMode(one.key)}
              >
                <one.icon />
                {one.label}
              </DropdownMenuCheckItem>
            ))}
          </DropdownMenuSubContent>
        </DropdownMenuSub>
        <DropdownMenuSeparator />
        <DropdownMenuItem tone="danger" onSelect={signOut}>
          <LogOut />
          Chiqish
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

/* ------------------------------------------------------------------- wording */

function initials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean)
  if (words.length === 0) return "?"
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase()
  return (words[0][0] + words[1][0]).toUpperCase()
}

function roleWord(role: string): string {
  if (role === "admin") return "Administrator"
  if (role === "warehouse") return "Ombor xodimi"
  if (role === "seller") return "Sotuvchi"
  if (role === "courier") return "Kuryer"
  return role
}
